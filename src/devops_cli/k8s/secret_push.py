"""Push the cluster Secret table from the workstation keyring: workstation keyring → cluster.

The reverse of `devops k8s sync-secrets`, which copies chart-generated credentials into the
keyring. A run first plans every value in memory (`plan_push`) and writes nothing when any
source is missing, a live value differs without `--rotate`, or the keyring is locked. Writing
(`execute_push`) stores adopted and generated values in the keyring first, then server-side
applies every Secret as one `List` on stdin, so no value reaches argv, a file, an annotation, a
log record or the output.

A dry run (`dry_run_push`) makes no request at all: it lists, from the table and the options
alone, the requests a push would make, in order, with placeholders where values would go.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, assert_never

from devops_cli.config.constants import CONST_KEYRING_SERVICE, CONST_KEYRING_UNLOCK_PROBE_KEY
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.config.options import K8S_GITHUB_ACCOUNT
from devops_cli.config.settings import (
    SecretStorageError,
    keyring_read,
    keyring_write,
    require_persistent_keyring,
)
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest, both
from devops_cli.exceptions.k8s import ClusterSecretPushError, ClusterSecretWriteError
from devops_cli.k8s.cluster_secrets import (
    FIELD_MANAGER,
    ClusterSecret,
    GitHubAccountSource,
    KeyringSource,
    LiteralSource,
    SecretEntry,
    SecretKeyRef,
    SecretSource,
    SettingSource,
)

LAST_APPLIED_ANNOTATION = "kubectl.kubernetes.io/last-applied-configuration"
GITHUB_HOST = "github.com"
# gh reaches its keyring over the session bus and finds its login state in its config dir.
_GH_ENV = frozenset(
    {"DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "GH_CONFIG_DIR", "XDG_CONFIG_HOME"}
)
# Names and resource versions only: the applied objects carry the values.
_APPLY_OUTPUT = (
    "jsonpath={range .items[*]}{.metadata.namespace}/{.metadata.name} "
    '{.metadata.resourceVersion}{"\\n"}{end}'
)


class EntryState(StrEnum):
    """What a push does, or would do, with one key."""

    CREATED = "created"
    UNCHANGED = "unchanged"
    ADOPTED = "adopted"
    GENERATED = "generated"
    ROTATED = "rotated"
    SKIPPED = "skipped"
    DIFFERS = "differs"
    MISSING = "missing"
    INVALID = "invalid"


BLOCKING_STATES = frozenset({EntryState.DIFFERS, EntryState.MISSING, EntryState.INVALID})
_PLAN_LABELS: dict[EntryState, str] = {
    EntryState.CREATED: "would create",
    EntryState.ADOPTED: "would adopt",
    EntryState.GENERATED: "would generate",
    EntryState.ROTATED: "would rotate",
    EntryState.SKIPPED: "would skip",
}


@dataclass(frozen=True)
class PushOptions:
    """How a push runs. `strict_namespaces` (`--only`) fails on a missing namespace.

    `github_account` is `--github-account`; without it the `k8s.github_account` setting is
    read, and only when a selected Secret needs the gh account.
    """

    context: str | None = None
    github_account: str | None = None
    rotate: bool = False
    restart: bool = True
    strict_namespaces: bool = False


@dataclass(frozen=True)
class LiveSecret:
    """A Secret as the cluster holds it: decoded data, field ownership and whether a
    client-side apply left its copy of the values in an annotation.

    `data` holds live values and is left out of the repr, and the annotation itself is not
    kept, since it carries the values in plain text.
    """

    data: dict[str, str] = field(repr=False)
    has_last_applied: bool
    owned_keys: frozenset[str]
    foreign_keys: frozenset[str]

    @classmethod
    def from_object(cls, obj: dict[str, Any]) -> LiveSecret:
        """Read a `kubectl get secret -o json` object."""
        metadata = obj.get("metadata") or {}
        managed = metadata.get("managedFields") or []
        return cls(
            data={key: _decode(raw) for key, raw in (obj.get("data") or {}).items()},
            has_last_applied=LAST_APPLIED_ANNOTATION in (metadata.get("annotations") or {}),
            owned_keys=_data_keys_of(managed, mine=True),
            foreign_keys=_data_keys_of(managed, mine=False),
        )


@dataclass
class EntryPlan:
    """One key's resolution. `value` is held in memory only and never printed."""

    entry: SecretEntry
    state: EntryState
    value: str | None = field(default=None, repr=False)
    store_key: str | None = None
    problem: str = ""


@dataclass
class SecretPlan:
    """One Secret's resolution, and what writing it did."""

    secret: ClusterSecret
    live: LiveSecret | None
    entries: list[EntryPlan]
    restarted: list[str] = field(default_factory=list)
    restart_commands: list[str] = field(default_factory=list)

    def data(self) -> dict[str, str]:
        """The keys to write, with their values."""
        return {
            plan.entry.key: plan.value
            for plan in self.entries
            if plan.value is not None and plan.state not in BLOCKING_STATES
        }

    def changed(self) -> bool:
        """Whether writing changes an existing Secret's data: a key added, changed or removed."""
        if self.live is None:
            return False
        desired = self.data()
        removed = self.live.owned_keys - desired.keys() - self.live.foreign_keys
        return bool(removed) or any(self.live.data.get(k) != v for k, v in desired.items())

    def leaked_annotation(self) -> bool:
        """Whether the live Secret carries a client-side apply's copy of its values."""
        return self.live is not None and self.live.has_last_applied


@dataclass
class PushPlan:
    """Every selected Secret's resolution, and the Secrets skipped for a missing namespace."""

    secrets: list[SecretPlan]
    skipped_namespaces: list[ClusterSecret] = field(default_factory=list)

    def problems(self) -> list[EntryPlan]:
        """The entries that stop the push."""
        return [
            entry
            for plan in self.secrets
            for entry in plan.entries
            if entry.state in BLOCKING_STATES
        ]


class PushMode(StrEnum):
    """How a push runs: write, read to plan, or make no request at all."""

    PUSH = "push"
    PLAN = "plan"
    DRY_RUN = "dry-run"


@dataclass(frozen=True)
class PushResult:
    """What a push returns, whatever its mode.

    A push or `--plan` carries the resolved `plan` (states, and the workloads restarted or that
    would be). A dry run resolves nothing, so its `plan` is None, and `requests` lists the
    requests a push would make, in order, with placeholders and no value.
    """

    mode: PushMode
    plan: PushPlan | None = None
    requests: tuple[PlannedRequest, ...] = ()

    @property
    def dry_run(self) -> bool:
        """Whether this is a dry run's result, which made no request."""
        return self.mode is PushMode.DRY_RUN


def _decode(raw: object) -> str:
    """Decode a Secret's base64 field with the standard library, losslessly.

    Bytes that are not UTF-8 decode to lone surrogates (`surrogateescape`), so a comparison
    with any keyring value sees the difference, and `_is_text` refuses to adopt such a value
    rather than store a mangled copy.
    """
    return base64.b64decode(str(raw)).decode("utf-8", errors="surrogateescape") if raw else ""


def _is_text(value: str) -> bool:
    """Whether a value decoded from a Secret was UTF-8 text."""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _encode(value: str) -> str:
    """Encode a value for a Secret's `data` with the standard library."""
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _data_keys_of(managed_fields: Iterable[dict[str, Any]], *, mine: bool) -> frozenset[str]:
    """The `data` keys this push's field manager owns (`mine`), or that any other manager owns."""
    keys: set[str] = set()
    for managed in managed_fields:
        if (managed.get("manager") == FIELD_MANAGER) != mine:
            continue
        data_fields = (managed.get("fieldsV1") or {}).get("f:data") or {}
        keys.update(name.removeprefix("f:") for name in data_fields if name.startswith("f:"))
    return frozenset(keys)


def _kubectl_argv(args: Sequence[str], context: str | None) -> list[str]:
    """The kubectl argv a push runs, the dry run's list included."""
    return ["kubectl", *args, *(["--context", context] if context else [])]


def _namespace_args(namespace: str) -> list[str]:
    return ["get", "namespace", namespace, "--ignore-not-found", "-o", "name"]


def _secret_args(namespace: str, name: str) -> list[str]:
    """`secret/NAME` rather than `secret NAME`: the output masker hides a word after "secret",
    which would turn a printed command into `kubectl get secret <masked-token>`."""
    return ["get", f"secret/{name}", "-n", namespace, "--ignore-not-found", "-o", "json"]


def _kubectl(
    args: Sequence[str],
    context: str | None,
    *,
    stdin: str | None = None,
    withheld: str | None = None,
) -> str:
    """Run kubectl and return its stdout, raising with its stderr when it fails.

    A call whose stdin carries values passes `withheld`, which replaces kubectl's stderr in
    the error: kubectl may quote any part of its input there.
    """
    result = run_subprocess(
        _kubectl_argv(args, context),
        input=stdin,
        quiet=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        detail = withheld or (result.stderr or "").strip()[:256]
        raise ClusterSecretPushError(
            f"`kubectl {' '.join(args[:2])}` exited {result.returncode}: {detail}"
        )
    return result.stdout or ""


def namespace_exists(namespace: str, context: str | None) -> bool:
    """Whether the namespace exists; a failing kubectl raises rather than reads as absent."""
    return bool(_kubectl(_namespace_args(namespace), context).strip())


def _fetch_live(namespace: str, name: str, context: str | None) -> LiveSecret | None:
    """The live Secret, read once, or None when it does not exist."""
    raw = _kubectl(_secret_args(namespace, name), context)
    return LiveSecret.from_object(json.loads(raw)) if raw.strip() else None


class _LiveSecrets:
    """Live Secrets read at most once each, including Secrets a value is adopted from."""

    def __init__(self, context: str | None) -> None:
        self._context = context
        self._cache: dict[tuple[str, str], LiveSecret | None] = {}

    def get(self, namespace: str, name: str) -> LiveSecret | None:
        key = (namespace, name)
        if key not in self._cache:
            self._cache[key] = _fetch_live(namespace, name, self._context)
        return self._cache[key]

    def value(self, ref: SecretKeyRef) -> str | None:
        live = self.get(ref.namespace, ref.name)
        return (live.data.get(ref.key) or None) if live else None


def _gh(args: list[str]) -> str:
    """Run one of gh's own `gh auth` commands and return its stdout.

    `gh auth` is local to gh (`is_local_gh_command`), so the child gets no session token: gh
    answers from its own store for the account named, never as the person running the push.
    """
    result = run_subprocess(
        ["gh", *args],
        extra_allowed_env=_GH_ENV,
        quiet=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise ClusterSecretPushError(f"`gh {' '.join(args[:2])}` failed")
    return (result.stdout or "").strip()


_GH_STATUS_ARGS = ["auth", "status", "--hostname", GITHUB_HOST, "--json", "hosts"]
# The state `gh auth status` gives an account whose stored token it checked and found working.
_GH_ACCOUNT_OK = "success"


def _gh_token_args(login: str) -> list[str]:
    """`--user` first: the output masker hides a 10-character word after "token", such as
    `--hostname`, which would mangle the printed command."""
    return ["auth", "token", "--user", login, "--hostname", GITHUB_HOST]


def read_github_account_token(login: str) -> str:
    """The token gh keeps in the OS keyring for `login`, as gh's own record vouches for it.

    `gh auth status` lists the accounts gh stores, each with the login gh recorded for its token
    and the state of gh's own check of that token; `gh auth token --user` then reads it. The push
    never calls GitHub with the token itself, so the process keeps its one identity (#767).
    Raises ClusterSecretPushError when gh has no such account, keeps its token in gh's config
    file rather than the keyring, or reports the token as not working.
    """
    status = json.loads(_gh(_GH_STATUS_ARGS) or "{}")
    accounts = [
        entry
        for entry in (status.get("hosts") or {}).get(GITHUB_HOST) or []
        if entry.get("login") == login
    ]
    if not accounts:
        raise ClusterSecretPushError(
            f"gh has no {GITHUB_HOST} account {login}; run `gh auth login`"
        )
    # An ambient GH_TOKEN of the same login is listed too, with the variable as its source.
    account = next((entry for entry in accounts if entry.get("tokenSource") == "keyring"), None)
    if account is None:
        raise ClusterSecretPushError(
            f"gh keeps {login}'s token in its config file, not the OS keyring; unlock the keyring "
            "and log the account in again"
        )
    if account.get("state") != _GH_ACCOUNT_OK:
        raise ClusterSecretPushError(
            f"gh reports {login}'s token as {account.get('state') or 'unchecked'}; run "
            f"`gh auth status --hostname {GITHUB_HOST}` and log the account in again"
        )
    token = _gh(_gh_token_args(login))
    if not token:
        raise ClusterSecretPushError(f"gh printed no token for {login}")
    return token


class _Sources:
    """Each source read once. Values a plan adopts or generates count as the keyring's own."""

    def __init__(self, github_account: str | None) -> None:
        self._github_account = github_account
        self._keyring: dict[str, str | None] = {}
        self._github: tuple[str | None, str] | None = None

    def read(self, source: SecretSource) -> tuple[str | None, str]:
        """The source's value, or None and why it has none."""
        match source:
            case KeyringSource(key=key):
                if key not in self._keyring:
                    self._keyring[key] = keyring_read(key)
                return self._keyring[key], ""
            case GitHubAccountSource():
                if self._github is None:
                    self._github = self._read_github()
                return self._github
            case SettingSource(option=option):
                return _setting(option), ""
            case LiteralSource(value=value):
                return value, ""
            case _:
                assert_never(source)

    def plan_store(self, key: str, value: str) -> None:
        """Count a value the push will store as the keyring's, for later entries of the key."""
        self._keyring[key] = value

    def _read_github(self) -> tuple[str | None, str]:
        account = self._github_account or _setting(K8S_GITHUB_ACCOUNT)
        if not account:
            return (
                None,
                "the machine account is unset: pass --github-account or set k8s.github_account",
            )
        try:
            return read_github_account_token(account), ""
        except (ClusterSecretPushError, json.JSONDecodeError) as exc:
            return None, str(exc) or type(exc).__name__


def _setting(option: str) -> str | None:
    """A non-secret setting's value, or None when unset."""
    from devops_cli.config.settings import dotted_get, load_settings

    value = dotted_get(load_settings(), option)
    return str(value) if value not in (None, "") else None


def _missing_hint(secret: ClusterSecret, entry: SecretEntry, reason: str) -> str:
    """Why a value is missing, naming where it would come from."""
    source = entry.source
    if reason:
        return f"{secret.ref} {entry.key}: {reason}"
    if isinstance(source, KeyringSource):
        adopt = entry.adopt_from or SecretKeyRef(secret.namespace, secret.name, entry.key)
        store = f"; store it with `devops config set {source.option}`" if source.option else ""
        return (
            f"{secret.ref} {entry.key}: keyring {source.key} is empty and {adopt} holds no "
            f"value{store}"
        )
    return f"{secret.ref} {entry.key}: {source.label} has no value"


def _absent(secret: ClusterSecret, entry: SecretEntry, reason: str) -> EntryPlan:
    """A value no source holds: a required entry fails, an optional one is skipped."""
    state = EntryState.MISSING if entry.required else EntryState.SKIPPED
    return EntryPlan(entry, state, problem=_missing_hint(secret, entry, reason))


def _compare(
    secret: ClusterSecret,
    entry: SecretEntry,
    value: str,
    live: str | None,
    rotate: bool,
    *,
    origin: str,
) -> EntryPlan:
    """A value from `origin` (the source, or the live key it is adopted from) against the live
    one."""
    if entry.value_prefix and not value.startswith(entry.value_prefix):
        problem = f"{secret.ref} {entry.key}: {origin} does not start with `{entry.value_prefix}`"
        return EntryPlan(entry, EntryState.INVALID, problem=problem)
    if live is None:
        return EntryPlan(entry, EntryState.CREATED, value)
    if live == value:
        return EntryPlan(entry, EntryState.UNCHANGED, value)
    if rotate:
        return EntryPlan(entry, EntryState.ROTATED, value)
    return EntryPlan(entry, EntryState.DIFFERS, problem=f"{secret.ref} {entry.key}")


def _plan_entry(
    secret: ClusterSecret,
    entry: SecretEntry,
    live: LiveSecret | None,
    sources: _Sources,
    lives: _LiveSecrets,
    rotate: bool,
) -> EntryPlan:
    """Resolve one key: the source's value, else adopt the live one, else generate, else fail."""
    value, reason = sources.read(entry.source)
    live_value = live.data.get(entry.key) if live else None
    if value is not None:
        return _compare(secret, entry, value, live_value, rotate, origin=entry.source.label)
    if not isinstance(entry.source, KeyringSource):
        return _absent(secret, entry, reason)
    adopt_ref = entry.adopt_from or SecretKeyRef(secret.namespace, secret.name, entry.key)
    adopted, state, origin = lives.value(adopt_ref), EntryState.ADOPTED, f"live {adopt_ref}"
    if adopted is not None and not _is_text(adopted):
        problem = f"{secret.ref} {entry.key}: {origin} is not UTF-8 text, so it is not adopted"
        return EntryPlan(entry, EntryState.INVALID, problem=problem)
    if adopted is None and entry.generator is not None:
        adopted, state, origin = entry.generator.generate(), EntryState.GENERATED, "generated"
    if adopted is None:
        return _absent(secret, entry, reason)
    planned = _compare(secret, entry, adopted, live_value, rotate, origin=origin)
    if planned.state in BLOCKING_STATES:
        return planned
    sources.plan_store(entry.source.key, adopted)
    return EntryPlan(entry, state, adopted, store_key=entry.source.key)


def _present(
    selected: Sequence[ClusterSecret], options: PushOptions
) -> tuple[list[ClusterSecret], list[ClusterSecret]]:
    """The Secrets whose namespace exists, and those skipped; `--only` fails on a missing one."""
    existing = {
        ns: namespace_exists(ns, options.context)
        for ns in dict.fromkeys(s.namespace for s in selected)
    }
    missing = [secret for secret in selected if not existing[secret.namespace]]
    if missing and options.strict_namespaces:
        names = ", ".join(sorted({secret.namespace for secret in missing}))
        raise ClusterSecretPushError(f"Namespace not found: {names}. Apply its manifests first.")
    return [secret for secret in selected if existing[secret.namespace]], missing


def plan_push(selected: Sequence[ClusterSecret], options: PushOptions) -> PushPlan:
    """Resolve every selected Secret in memory, writing nothing anywhere.

    The keyring is checked before anything is read, and namespaces before any source, so a
    Secret skipped for its namespace has its sources neither read nor required.
    """
    require_persistent_keyring()
    present, skipped = _present(selected, options)
    sources = _Sources(options.github_account)
    lives = _LiveSecrets(options.context)
    plans: list[SecretPlan] = []
    for secret in present:
        live = lives.get(secret.namespace, secret.name)
        entries = [
            _plan_entry(secret, entry, live, sources, lives, options.rotate)
            for entry in secret.entries
        ]
        plans.append(SecretPlan(secret, live, entries))
    return PushPlan(plans, skipped)


def describe_problems(plan: PushPlan) -> str:
    """One message naming every missing source and every differing live value."""
    problems = plan.problems()
    differs = [entry.problem for entry in problems if entry.state is EntryState.DIFFERS]
    others = [entry.problem for entry in problems if entry.state is not EntryState.DIFFERS]
    parts = []
    if others:
        parts.append("Missing or invalid sources: " + "; ".join(others) + ".")
    if differs:
        parts.append(
            "Live values differ from the keyring: " + ", ".join(differs) + ". Rerun with "
            "--rotate to replace them with the keyring's, or delete the keyring entry to adopt "
            "the live value."
        )
    return " ".join(parts)


def _secret_manifest(secret: ClusterSecret, data: dict[str, str]) -> dict[str, Any]:
    """The Secret as applied: `data` (base64-encoded values) and no annotations."""
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "type": "Opaque",
        "metadata": {
            "name": secret.name,
            "namespace": secret.namespace,
            "labels": secret.manifest_labels(),
        },
        "data": data,
    }


def _list_manifest(items: list[dict[str, Any]], indent: int | None = None) -> str:
    """The `List` a push applies on stdin; a dry run's is indented for reading."""
    return json.dumps({"apiVersion": "v1", "kind": "List", "items": items}, indent=indent)


_APPLY_ARGS = [
    "apply",
    "--server-side",
    f"--field-manager={FIELD_MANAGER}",
    "--force-conflicts",
    "-f",
    "-",
    "-o",
    _APPLY_OUTPUT,
]


def _store_in_keyring(plan: PushPlan, done: list[str]) -> None:
    """Store adopted and generated values before the cluster is written, so none is lost."""
    stores = {
        entry.store_key: entry.value
        for p in plan.secrets
        for entry in p.entries
        if entry.store_key and entry.value
    }
    stored: list[str] = []
    try:
        for key, value in stores.items():
            keyring_write(key, value)
            stored.append(key)
    finally:
        if stored:
            done.append("keyring entries stored: " + ", ".join(stored))


def _apply(plans: Sequence[SecretPlan], context: str | None) -> None:
    """Server-side apply every Secret as one `List` on stdin under the devops-cli field manager.

    kubectl's stderr is not shown on failure: a parse or validation error may quote stdin.
    """
    manifest = _list_manifest(
        [_secret_manifest(p.secret, {k: _encode(v) for k, v in p.data().items()}) for p in plans]
    )
    names = ", ".join(p.secret.ref for p in plans)
    withheld = f"applying {names}; its error output is not shown, since it may quote values"
    _kubectl(_APPLY_ARGS, context, stdin=manifest, withheld=withheld)


def _remove_leaked_annotation(plan: SecretPlan, context: str | None) -> None:
    """Drop the last-applied copy a client-side apply left on the Secret."""
    _kubectl(_annotate_args(plan.secret), context)


def _annotate_args(secret: ClusterSecret) -> list[str]:
    return [
        "annotate",
        f"secret/{secret.name}",
        "-n",
        secret.namespace,
        f"{LAST_APPLIED_ANNOTATION}-",
    ]


def _workload_args(workload: str, namespace: str) -> list[str]:
    return ["get", workload, "-n", namespace, "--ignore-not-found", "-o", "name"]


def _rollout_args(workload: str, namespace: str) -> list[str]:
    return ["rollout", "restart", workload, "-n", namespace]


def _existing_workloads(plan: SecretPlan, context: str | None) -> list[str]:
    """The Secret's restart targets that exist, read with `kubectl get` only."""
    namespace = plan.secret.namespace
    return [
        str(workload)
        for workload in plan.secret.restarts
        if _kubectl(_workload_args(str(workload), namespace), context).strip()
    ]


def _restart(plan: SecretPlan, options: PushOptions, *, preview: bool = False) -> None:
    """Restart the existing workloads of a Secret whose data changed, or list the commands.

    A preview (`--plan`) lists the workloads it would restart and runs no restart.
    """
    for workload in _existing_workloads(plan, options.context):
        args = _rollout_args(workload, plan.secret.namespace)
        if not options.restart:
            context = f" --context {options.context}" if options.context else ""
            plan.restart_commands.append(f"kubectl {' '.join(args)}{context}")
            continue
        if not preview:
            _kubectl(args, options.context)
        plan.restarted.append(workload)


def _needs_restart(plan: SecretPlan) -> bool:
    """Whether the push changes an existing Secret it writes."""
    return bool(plan.data()) and plan.changed()


def preview_restarts(plan: PushPlan, options: PushOptions) -> None:
    """For `--plan`: the existing workloads each changed Secret would restart, read only."""
    for secret_plan in plan.secrets:
        if _needs_restart(secret_plan):
            _restart(secret_plan, options, preview=True)


def _write(plan: PushPlan, options: PushOptions, done: list[str]) -> None:
    """Keyring first, then one apply, annotations and restarts, recording each step in `done`."""
    _store_in_keyring(plan, done)
    to_apply = [p for p in plan.secrets if p.data()]
    if to_apply:
        _apply(to_apply, options.context)
        done.append("Secrets applied: " + ", ".join(p.secret.ref for p in to_apply))
    for secret_plan in plan.secrets:
        if secret_plan.leaked_annotation():
            _remove_leaked_annotation(secret_plan, options.context)
            done.append(f"last-applied annotation removed from {secret_plan.secret.ref}")
        if _needs_restart(secret_plan):
            try:
                _restart(secret_plan, options)
            finally:
                if secret_plan.restarted:
                    restarted = ", ".join(secret_plan.restarted)
                    done.append(f"{secret_plan.secret.ref} workloads restarted: {restarted}")


def execute_push(plan: PushPlan, options: PushOptions) -> None:
    """Write a plan without problems: keyring first, then one apply, annotations and restarts.

    A failure part-way raises `ClusterSecretWriteError` naming the steps already done.
    """
    if plan.problems():
        raise ClusterSecretPushError(describe_problems(plan))
    done: list[str] = []
    try:
        _write(plan, options, done)
    except (SecretStorageError, ClusterSecretPushError) as exc:
        raise ClusterSecretWriteError(str(exc), completed=tuple(done)) from exc


def reads_github(plan: PushPlan) -> bool:
    """Whether resolving the plan read the machine account's token from gh and GitHub."""
    return any(
        isinstance(entry.entry.source, GitHubAccountSource)
        for secret_plan in plan.secrets
        for entry in secret_plan.entries
    )


def state_label(state: EntryState, *, preview: bool) -> str:
    """How output names a state; a preview (`--plan`) says what a push would do."""
    return _PLAN_LABELS.get(state, state.value) if preview else state.value


def secret_line(plan: SecretPlan, *, preview: bool) -> str:
    """One output line per Secret: keys with their source and state, and restarts. No value."""
    keys = ", ".join(
        f"{entry.entry.key} ({entry.entry.source.label}) "
        f"{state_label(entry.state, preview=preview)}"
        for entry in plan.entries
    )
    restarted = ", ".join(plan.restarted) or "none"
    label = "would restart" if preview else "restarted"
    return f"{plan.secret.ref}: {keys}; {label}: {restarted}"


# ── Dry run: the requests a push makes, made by nobody ─────────────────────

_ACCOUNT_PLACEHOLDER = f"<{K8S_GITHUB_ACCOUNT}>"


class _RequestPlan:
    """The requests a push makes, in the order `plan_push` and `execute_push` make them.

    Built from the table and the options alone. Each condition is a tuple of parts that must all
    hold. A read the push caches (`once`) is listed again only where an earlier listing's
    condition may not have held, to run unless it was done above.
    """

    def __init__(self, options: PushOptions) -> None:
        self.options = options
        self._listed: dict[str, frozenset[str]] = {}
        self.requests: list[PlannedRequest] = []

    def _add(self, request: PlannedRequest, when: tuple[str, ...], once: str) -> None:
        parts = frozenset(when)
        if once:
            earlier = self._listed.get(once)
            if earlier is not None and earlier <= parts:
                return
            self._listed[once] = parts
            if earlier is not None:
                when = (*when, "not done above")
        self.requests.append(replace(request, condition=both(*when)))

    def kubectl(
        self,
        args: Sequence[str],
        target: str,
        when: tuple[str, ...] = (),
        *,
        once: bool = False,
        stdin: str | None = None,
    ) -> None:
        argv = tuple(_kubectl_argv(args, self.options.context))
        request = PlannedRequest(f"kubectl {args[0]}", target, argv, stdin=stdin)
        self._add(request, when, f"kubectl {target}" if once else "")

    def keyring(self, method: str, key: str, when: tuple[str, ...] = ()) -> None:
        target = f"{CONST_KEYRING_SERVICE}/{key}"
        self._add(PlannedRequest(f"keyring {method}", target), when, f"keyring {method} {key}")

    def gh(self, when: tuple[str, ...]) -> None:
        """The machine account's token: gh's accounts, then its token once gh's record lists
        it as `read_github_account_token` needs."""
        login = self.options.github_account or _ACCOUNT_PLACEHOLDER
        if not self.options.github_account:
            when = (*when, f"{K8S_GITHUB_ACCOUNT} is set")
        for args, after in (
            (_GH_STATUS_ARGS, ()),
            (
                _gh_token_args(login),
                (f"gh auth status lists {login} with a working token in the keyring",),
            ),
        ):
            method = f"gh {' '.join(args[:2])}"
            request = PlannedRequest(method, GITHUB_HOST, ("gh", *args))
            self._add(request, (*when, *after), method)


def _placeholder(entry: SecretEntry) -> str:
    """What stands in an applied Secret's `data` for an entry's value."""
    optional = ", left out when it has none" if not entry.required else ""
    return f"<base64 of {entry.source.label}{optional}>"


def _plan_reads(requests: _RequestPlan, secret: ClusterSecret, present: tuple[str, ...]) -> None:
    """The reads `plan_push` makes for one Secret: the live Secret, then each entry's sources."""
    requests.kubectl(_secret_args(secret.namespace, secret.name), secret.ref, present, once=True)
    for entry in secret.entries:
        match entry.source:
            case KeyringSource(key=key):
                requests.keyring("read", key, present)
                adopt = entry.adopt_from or SecretKeyRef(secret.namespace, secret.name, entry.key)
                requests.kubectl(
                    _secret_args(adopt.namespace, adopt.name),
                    f"{adopt.namespace}/{adopt.name}",
                    (*present, f"keyring {key} is empty"),
                    once=True,
                )
            case GitHubAccountSource():
                requests.gh(present)
            case SettingSource() | LiteralSource():
                pass
            case _:
                assert_never(entry.source)


def _plan_writes(requests: _RequestPlan, selected: Sequence[ClusterSecret]) -> None:
    """The writes `execute_push` makes: keyring stores, one apply, annotations and restarts."""
    options = requests.options
    for secret in selected:
        for entry in secret.entries:
            if isinstance(entry.source, KeyringSource):
                key = entry.source.key
                stored = f"keyring {key} was empty and a value was adopted or generated"
                requests.keyring("write", key, (*_when_present(secret, options), stored))
    items = [
        _secret_manifest(secret, {e.key: _placeholder(e) for e in secret.entries})
        for secret in selected
    ]
    requests.kubectl(
        _APPLY_ARGS,
        ", ".join(secret.ref for secret in selected),
        (_ALL_PRESENT,) if options.strict_namespaces else (_LEFT_OUT,),
        stdin=_list_manifest(items, indent=2),
    )
    for secret in selected:
        present = _when_present(secret, options)
        leaked = f"live {secret.ref} carries {LAST_APPLIED_ANNOTATION}"
        requests.kubectl(_annotate_args(secret), secret.ref, (*present, leaked))
        changed = (*present, f"the push changes live {secret.ref}'s data")
        for workload in map(str, secret.restarts):
            requests.kubectl(_workload_args(workload, secret.namespace), workload, changed)
        for workload in map(str, secret.restarts) if options.restart else ():
            requests.kubectl(
                _rollout_args(workload, secret.namespace),
                workload,
                (*changed, f"{workload} exists"),
            )


_LEFT_OUT = "a namespace exists; a Secret whose namespace is missing is left out"
_ALL_PRESENT = "every selected namespace exists"


def _when_present(secret: ClusterSecret, options: PushOptions) -> tuple[str, ...]:
    """When a Secret's requests run: `--only` stops on a missing namespace, `--stack` skips it."""
    if options.strict_namespaces:
        return (_ALL_PRESENT,)
    return (f"namespace {secret.namespace} exists",)


def dry_run_push(selected: Sequence[ClusterSecret], options: PushOptions) -> PushResult:
    """The requests a push of `selected` would make, in order, making none.

    Nothing is read: not the keyring, the cluster, gh nor the settings. Values appear as named
    placeholders, and a request that depends on an earlier answer names it as its condition.
    """
    requests = _RequestPlan(options)
    requests.keyring("read", CONST_KEYRING_UNLOCK_PROBE_KEY)
    for namespace in dict.fromkeys(secret.namespace for secret in selected):
        requests.kubectl(_namespace_args(namespace), f"namespace {namespace}")
    for secret in selected:
        _plan_reads(requests, secret, _when_present(secret, options))
    _plan_writes(requests, selected)
    return PushResult(PushMode.DRY_RUN, requests=tuple(requests.requests))
