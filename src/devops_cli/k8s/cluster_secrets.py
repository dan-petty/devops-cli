"""The Secrets a cluster's stacks read, and where each of their values comes from.

One table, held as data, is the single list of what a cluster needs: `devops k8s push-secrets`
and `devops k8s deploy-stack` write every row from the workstation's keyring, and a gate test
fails on any Secret a manifest or values file under k8s/ references without a row. Each row
lands with the item that adds the Secret's consumer.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import quote

from devops_cli.config.constants import (
    CONST_GITHUB_APP_PRIVATE_KEY_ENV,
    CONST_K8S_GITEA_ADMIN_USER,
    CONST_K8S_MATTERMOST_URL,
)
from devops_cli.config.env import credential

MANAGED_BY_LABEL = "app.kubernetes.io/managed-by"
MANAGED_BY_VALUE = "devops-cli"
FIELD_MANAGER = "devops-cli"

# Rows of `base` belong to the root kustomization, which every deploy-stack run applies.
BASE_STACK = "base"
# Stacks deploy-stack never deploys. Their rows are pushed wherever their namespace exists.
DETACHED_STACKS: tuple[str, ...] = ("devops",)

# Generated values nobody types live under keyring-only keys; no Settings option reads them.
LLM_GATEWAY_MASTER_KEY = "llm_gateway_master_key"
# The password of devops-cli's cache Valkey in the cluster (#1655). A workstation's
# `valkey.password` is the password of the Valkey that its own `valkey.url` names.
DEVOPS_CACHE_VALKEY_AUTH_KEY = "valkey_devops_password"
# LiteLLM refuses a master key without this prefix.
LITELLM_KEY_PREFIX = "sk-"
# The database password of Mattermost on CloudNativePG (#1391).
MATTERMOST_DB_AUTH_KEY = "mattermost_db_password"
_BASIC_AUTH_SECRET_TYPE: SecretType = "kubernetes.io/basic-auth"


@dataclass(frozen=True)
class KeyringSource:
    """A keyring entry. `option` names the managed credential it backs; None for keyring-only."""

    key: str
    option: str | None = None

    @classmethod
    def for_credential(cls, option: str) -> KeyringSource:
        """The keyring entry of the managed credential `option`, as `CREDENTIALS` names it."""
        return cls(credential(option).keyring_name, option)

    @property
    def label(self) -> str:
        """How output names the source, never its value."""
        return f"keyring {self.key}"


@dataclass(frozen=True)
class SettingSource:
    """A non-secret setting, such as a username."""

    option: str

    @property
    def label(self) -> str:
        """How output names the source."""
        return f"setting {self.option}"


@dataclass(frozen=True)
class LiteralSource:
    """A fixed, non-secret value, such as a URL."""

    value: str

    @property
    def label(self) -> str:
        """How output names the source."""
        return "literal"


PlainSource = KeyringSource | SettingSource | LiteralSource


@dataclass(frozen=True)
class DerivedSource:
    """A value built from other values of the same push, and never stored on its own.

    `template` is a `str.format` template whose fields name `inputs`. The push resolves every
    entry that is not derived first, so an input reads the value the push adopts or generates.
    Each input's value fills its field quoted with `urllib.parse.quote(..., safe="")`, so a
    credential in a URL keeps its own characters.
    """

    template: str
    inputs: Mapping[str, PlainSource] = field(hash=False)

    @property
    def label(self) -> str:
        """How output names the source: its inputs, never their values."""
        return "derived from " + ", ".join(source.label for source in self.inputs.values())

    def build(self, values: Mapping[str, str]) -> str:
        """The value, from the value of each input."""
        return self.template.format_map(
            {name: quote(values[name], safe="") for name in self.inputs}
        )


SecretSource = PlainSource | DerivedSource
# The Secret types the table writes. Kubernetes takes any other type as a custom one, so a
# typo would reach the cluster unseen; a row that needs another built-in type adds it here.
SecretType = Literal["Opaque", "kubernetes.io/basic-auth"]


@dataclass(frozen=True)
class SecretGenerator:
    """How a value nobody types is made: `prefix` and then `nbytes` random bytes, encoded."""

    encoding: Literal["hex", "urlsafe"]
    nbytes: int
    prefix: str = ""

    def generate(self) -> str:
        """A new random value from the standard library's `secrets`."""
        encode = secrets.token_hex if self.encoding == "hex" else secrets.token_urlsafe
        return self.prefix + encode(self.nbytes)


@dataclass(frozen=True)
class SecretKeyRef:
    """One key of one Secret."""

    namespace: str
    name: str
    key: str

    def __str__(self) -> str:
        return f"{self.namespace}/{self.name} {self.key}"


@dataclass(frozen=True)
class SecretEntry:
    """One key of a cluster Secret and how its value is resolved.

    A keyring value the keyring lacks is adopted from the live `adopt_from` key (the entry's
    own key when None), else made by `generator`; otherwise a required entry fails and an
    optional one is skipped. A derived value is never adopted or generated. Every value must
    start with `value_prefix`.
    """

    key: str
    source: SecretSource
    required: bool = True
    generator: SecretGenerator | None = None
    adopt_from: SecretKeyRef | None = None
    value_prefix: str = ""


@dataclass(frozen=True)
class Workload:
    """A workload `kubectl rollout restart` accepts."""

    kind: Literal["deployment", "statefulset", "daemonset"]
    name: str

    def __str__(self) -> str:
        return f"{self.kind}/{self.name}"


@dataclass(frozen=True)
class ClusterSecret:
    """A Secret the cluster needs, its type, the stack it belongs to and the workloads that
    read it. Kubernetes cannot change the type of a Secret, so a row names it before its first
    push."""

    namespace: str
    name: str
    stack: str
    entries: tuple[SecretEntry, ...]
    restarts: tuple[Workload, ...] = ()
    labels: dict[str, str] = field(default_factory=dict)
    change_note: str = ""
    secret_type: SecretType = "Opaque"

    @property
    def ref(self) -> str:
        """`namespace/name`."""
        return f"{self.namespace}/{self.name}"

    def manifest_labels(self) -> dict[str, str]:
        """The labels every pushed Secret carries, with its own."""
        return {**self.labels, MANAGED_BY_LABEL: MANAGED_BY_VALUE}


_LLM_GATEWAY_KEY = KeyringSource(LLM_GATEWAY_MASTER_KEY)
_DEVOPS_CACHE_VALKEY_AUTH = KeyringSource(DEVOPS_CACHE_VALKEY_AUTH_KEY)
_DEVOPS_CACHE_VALKEY_GENERATOR = SecretGenerator("hex", 32)

CLUSTER_SECRETS: tuple[ClusterSecret, ...] = (
    ClusterSecret(
        namespace="llm",
        name="llm-gateway-secrets",
        stack="llm",
        entries=(
            SecretEntry(
                "master-key",
                _LLM_GATEWAY_KEY,
                generator=SecretGenerator("hex", 24, prefix=LITELLM_KEY_PREFIX),
                value_prefix=LITELLM_KEY_PREFIX,
            ),
            # The keys of the hosted model groups. The gateway starts without them (#3113).
            SecretEntry(
                "gemini-api-key",
                KeyringSource.for_credential("gemini.api_key"),
                required=False,
            ),
            SecretEntry(
                "anthropic-api-key",
                KeyringSource.for_credential("anthropic.api_key"),
                required=False,
            ),
        ),
        restarts=(Workload("deployment", "llm-gateway"),),
        labels={"app.kubernetes.io/name": "llm-gateway"},
        change_note=(
            "Open WebUI keeps the gateway connection stored in its database: update the key "
            "under Admin Panel > Settings > Connections."
        ),
    ),
    # Qdrant requires the key, and Open WebUI reads it as QDRANT_API_KEY when its pod starts.
    ClusterSecret(
        namespace="llm",
        name="qdrant-api-key",
        stack="llm",
        entries=(
            SecretEntry(
                "api-key",
                KeyringSource.for_credential("qdrant.api_key"),
                generator=SecretGenerator("urlsafe", 32),
            ),
        ),
        restarts=(Workload("statefulset", "qdrant"), Workload("statefulset", "open-webui")),
        labels={"app.kubernetes.io/name": "qdrant"},
    ),
    ClusterSecret(
        namespace="llm",
        name="valkey-runs-auth",
        stack="llm",
        entries=(
            SecretEntry(
                "password",
                KeyringSource.for_credential("runs.index_password"),
                generator=SecretGenerator("hex", 32),
            ),
        ),
        restarts=(Workload("deployment", "valkey-runs"),),
        labels={"app.kubernetes.io/name": "valkey-runs"},
    ),
    # The cache Valkey's password, which a workstation sends through `devops k8s port-forward`.
    # Open WebUI loads the Secret with envFrom, so its key is the variable's name.
    ClusterSecret(
        namespace="llm",
        name="valkey-auth",
        stack="llm",
        entries=(
            SecretEntry(
                "VALKEY_PASSWORD",
                KeyringSource.for_credential("valkey.password"),
                generator=SecretGenerator("hex", 32),
            ),
        ),
        restarts=(Workload("deployment", "valkey"), Workload("statefulset", "open-webui")),
        labels={"app.kubernetes.io/name": "valkey"},
    ),
    # The password of devops-cli's cache Valkey, which the Service and the cluster jobs send from
    # Secret devops/devops-cli (#1655).
    ClusterSecret(
        namespace="llm",
        name="valkey-devops-auth",
        stack="llm",
        entries=(
            SecretEntry(
                "password",
                _DEVOPS_CACHE_VALKEY_AUTH,
                generator=_DEVOPS_CACHE_VALKEY_GENERATOR,
            ),
        ),
        restarts=(Workload("deployment", "valkey-devops"),),
        labels={"app.kubernetes.io/name": "valkey-devops"},
    ),
    ClusterSecret(
        namespace="cloudflared",
        name="cloudflared-token",
        stack=BASE_STACK,
        entries=(
            SecretEntry(
                "token",
                KeyringSource.for_credential("cloudflare.tunnel_token"),
                required=False,
            ),
        ),
        restarts=(Workload("deployment", "cloudflared"),),
        labels={"app.kubernetes.io/name": "cloudflared"},
    ),
    ClusterSecret(
        namespace="devops",
        name="devops-cli",
        stack="devops",
        entries=(
            # The GitHub App's private key: a pod whose environment holds it acts as the App
            # (ADR 0015). A person stores it with `devops config set --from-file`.
            SecretEntry(
                CONST_GITHUB_APP_PRIVATE_KEY_ENV,
                KeyringSource.for_credential("service.github_app.private_key"),
            ),
            SecretEntry(
                "DEVOPS_CLI_AI_API_KEY",
                _LLM_GATEWAY_KEY,
                adopt_from=SecretKeyRef("llm", "llm-gateway-secrets", "master-key"),
                value_prefix=LITELLM_KEY_PREFIX,
            ),
            SecretEntry(
                "DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS",
                KeyringSource.for_credential("service.webhook_secrets"),
                required=False,
            ),
            SecretEntry(
                "DEVOPS_CLI_FIRECRAWL_API_KEY",
                KeyringSource.for_credential("firecrawl.api_key"),
                required=False,
            ),
            # `valkey.password` of the pods: the password of the cache Valkey that the ConfigMap's
            # `valkey.url` names.
            SecretEntry(
                "DEVOPS_CLI_VALKEY_PASSWORD",
                _DEVOPS_CACHE_VALKEY_AUTH,
                generator=_DEVOPS_CACHE_VALKEY_GENERATOR,
                adopt_from=SecretKeyRef("llm", "valkey-devops-auth", "password"),
            ),
            SecretEntry(
                "DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN",
                KeyringSource.for_credential("mattermost.command_token"),
                required=False,
            ),
        ),
        restarts=(Workload("deployment", "roadmap-service"),),
        labels={"app.kubernetes.io/name": "devops-cli"},
    ),
    ClusterSecret(
        namespace="monitoring",
        name="grafana-admin",
        stack="infra",
        entries=(
            SecretEntry("admin-user", LiteralSource("admin")),
            SecretEntry(
                "admin-password",
                KeyringSource.for_credential("grafana.password"),
                generator=SecretGenerator("urlsafe", 32),
                adopt_from=SecretKeyRef("monitoring", "grafana", "admin-password"),
            ),
        ),
        restarts=(Workload("deployment", "grafana"),),
        labels={"app.kubernetes.io/name": "grafana"},
    ),
    ClusterSecret(
        namespace="monitoring",
        name="alertmanager-mattermost",
        stack="infra",
        entries=(
            SecretEntry(
                "url",
                DerivedSource(
                    f"{CONST_K8S_MATTERMOST_URL}/hooks/{{hook}}",
                    {"hook": KeyringSource.for_credential("mattermost.alerts_hook")},
                ),
                required=False,
            ),
        ),
        labels={"app.kubernetes.io/name": "alertmanager"},
    ),
    # The GitHub App of Argo CD's GitHub notifier (#2000). Its `service.github` refers to these
    # keys as `$github-appID`, `$github-installationID` and `$github-privateKey`. The values
    # (`notifications.secret.create: false`) leave this Secret to the push. Argo CD reads the
    # Secret when it builds each notification, so no workload restarts.
    ClusterSecret(
        namespace="argocd",
        name="argocd-notifications-secret",
        stack="infra",
        entries=(
            SecretEntry("github-appID", SettingSource("argocd.github_app_id"), required=False),
            SecretEntry(
                "github-installationID",
                SettingSource("argocd.github_app_installation_id"),
                required=False,
            ),
            SecretEntry(
                "github-privateKey",
                KeyringSource.for_credential("argocd.github_app_private_key"),
                required=False,
            ),
            SecretEntry(
                "mattermost-deploys-url",
                DerivedSource(
                    f"{CONST_K8S_MATTERMOST_URL}/hooks/{{hook}}",
                    {"hook": KeyringSource.for_credential("mattermost.deploys_hook")},
                ),
                required=False,
            ),
        ),
        labels={"app.kubernetes.io/part-of": "argocd"},
    ),
    # Gitea's admin (#1081). A person types the password, so the push never makes one. The user
    # is the chart's default, which Gitea does not reserve. Each start of Gitea sets the
    # admin's password to this Secret's (`gitea.admin.passwordMode: keepUpdated`).
    ClusterSecret(
        namespace="gitea",
        name="gitea-admin",
        stack="gitea",
        entries=(
            SecretEntry("username", LiteralSource(CONST_K8S_GITEA_ADMIN_USER)),
            SecretEntry("password", KeyringSource.for_credential("gitea.admin_password")),
        ),
        restarts=(Workload("deployment", "gitea"),),
        labels={"app.kubernetes.io/name": "gitea"},
    ),
    ClusterSecret(
        namespace="mattermost",
        name="mattermost-db",
        stack="chat",
        secret_type=_BASIC_AUTH_SECRET_TYPE,
        entries=(
            SecretEntry("username", LiteralSource("mattermost")),
            SecretEntry(
                "password",
                KeyringSource(MATTERMOST_DB_AUTH_KEY),
                generator=SecretGenerator("urlsafe", 32),
                adopt_from=SecretKeyRef("mattermost", "mattermost-db", "password"),
            ),
            SecretEntry(
                "DB_CONNECTION_STRING",
                DerivedSource(
                    "postgres://{username}:{password}@mattermost-db-rw.mattermost.svc.cluster.local:5432/mattermost?sslmode=require&connect_timeout=10",
                    {
                        "username": LiteralSource("mattermost"),
                        "password": KeyringSource(MATTERMOST_DB_AUTH_KEY),
                    },
                ),
            ),
        ),
        labels={"app.kubernetes.io/name": "mattermost-db"},
    ),
)


def secret_names(table: Iterable[ClusterSecret] = CLUSTER_SECRETS) -> list[str]:
    """Every `namespace/name` in the table, in its order."""
    return [secret.ref for secret in table]


def secrets_for_stacks(
    stacks: Iterable[str], table: Iterable[ClusterSecret] = CLUSTER_SECRETS
) -> tuple[ClusterSecret, ...]:
    """The rows of the given stacks, in table order."""
    wanted = set(stacks)
    return tuple(secret for secret in table if secret.stack in wanted)


def secrets_by_ref(
    refs: Iterable[str], table: Iterable[ClusterSecret] = CLUSTER_SECRETS
) -> tuple[tuple[ClusterSecret, ...], list[str]]:
    """The rows named `namespace/name`, in table order, and the names the table lacks."""
    wanted = list(dict.fromkeys(refs))
    rows = tuple(table)
    known = {secret.ref for secret in rows}
    return tuple(secret for secret in rows if secret.ref in wanted), [
        ref for ref in wanted if ref not in known
    ]


def table_stacks(table: Iterable[ClusterSecret] = CLUSTER_SECRETS) -> tuple[str, ...]:
    """The stacks the table's rows belong to, in table order."""
    return tuple(dict.fromkeys(secret.stack for secret in table))


def keyring_sources(entry: SecretEntry) -> tuple[KeyringSource, ...]:
    """The keyring entries an entry reads: its own source, or the inputs of a derived one."""
    source = entry.source
    sources = source.inputs.values() if isinstance(source, DerivedSource) else (source,)
    return tuple(s for s in sources if isinstance(s, KeyringSource))


def keyring_only_keys(table: Iterable[ClusterSecret] = CLUSTER_SECRETS) -> frozenset[str]:
    """The keyring keys the table declares that no Settings option reads."""
    return frozenset(
        source.key
        for secret in table
        for entry in secret.entries
        for source in keyring_sources(entry)
        if source.option is None
    )
