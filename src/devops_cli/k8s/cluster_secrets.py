"""The Secrets a cluster's stacks read, and where each of their values comes from.

One table, held as data, is the single list of what a cluster needs: `devops k8s push-secrets`
and `devops k8s deploy-stack` write every row from the workstation's keyring, and a gate test
fails on any Secret a manifest or values file under k8s/ references without a row. Each row
lands with the item that adds the Secret's consumer.
"""

from __future__ import annotations

import secrets
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal, Self
from urllib.parse import quote

import yaml
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    model_validator,
)

from devops_cli.config.constants import CONST_GITHUB_APP_PRIVATE_KEY_ENV
from devops_cli.config.env import credential
from devops_cli.exceptions import ConfigurationError

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
# The server secret of SearXNG (#3924). No Settings option reads it: only the pod does.
SEARXNG_SERVER_KEY = "searxng_secret_key"
# The password of the OpenMetrics endpoint of SearXNG (#4201). No Settings option reads it: the
# render-settings init container writes it into the settings file, and the scrape reads it.
SEARXNG_METRICS_AUTH_KEY = "searxng_metrics_password"
# The token that Grafana sends to its image renderer (#5185). No Settings option reads it: only
# the two pods do.
GRAFANA_RENDERER_AUTH_KEY = "grafana_renderer_token"
# The secret_key that Grafana uses to sign session cookies and CSRF tokens (#5697).
GRAFANA_SECURITY_KEY = "grafana_secret_key"
# The password of the admin UI of the object store (#4750). No Settings option reads it: a person
# reads it from the keyring to sign in through a port-forward.
SEAWEEDFS_ADMIN_AUTH_KEY = "seaweedfs_admin_password"
# The identities file of the S3 gateway of the object store: no identity. With a file, SeaweedFS
# refuses each request that no identity allows, and it adds the identities that the filer keeps:
# those of the admin UI, and identity `anonymous` of the anonymous read of the store buckets
# (k8s/object-store/buckets.yaml). With no file and no identity in the filer it allows every
# request.
SEAWEEDFS_S3_NO_IDENTITIES = '{"identities": []}'


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
    gate_namespace: str | None = None

    @property
    def ref(self) -> str:
        """`namespace/name`."""
        return f"{self.namespace}/{self.name}"

    def manifest_labels(self) -> dict[str, str]:
        """The labels every pushed Secret carries, with its own."""
        return {**self.labels, MANAGED_BY_LABEL: MANAGED_BY_VALUE}


CRAWL4AI_ENV_NAME = "CRAWL4AI_API_TOKEN"
_CRAWL4AI_TOKEN = KeyringSource.for_credential("crawl4ai.api_token")
MCP_SERVER_ENV_NAME = "DEVOPS_CLI_MCP_TOKEN"
_MCP_TOKEN = KeyringSource.for_credential("mcp.token")
_LLM_GATEWAY_KEY = KeyringSource(LLM_GATEWAY_MASTER_KEY)
_DEVOPS_CACHE_VALKEY_AUTH = KeyringSource(DEVOPS_CACHE_VALKEY_AUTH_KEY)
_DEVOPS_CACHE_VALKEY_GENERATOR = SecretGenerator("hex", 32)


class WorkloadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["deployment", "statefulset", "daemonset"]
    name: str


class GeneratorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    encoding: Literal["hex", "urlsafe"]
    nbytes: int
    prefix: str = ""


class AdoptFromModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    namespace: str
    name: str
    key: str


class KeyringSourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    option: str | None = None


class SettingSourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    option: str


class LiteralSourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str


class DerivedInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keyring: KeyringSourceModel | None = None
    setting: SettingSourceModel | None = None
    literal: LiteralSourceModel | None = None

    @model_validator(mode="after")
    def validate_one_source(self) -> Self:
        sources = [self.keyring, self.setting, self.literal]
        if sum(1 for s in sources if s is not None) != 1:
            raise ValueError("derived input must specify exactly one of: keyring, setting, literal")
        return self


class DerivedSourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template: str
    inputs: dict[str, DerivedInputModel] = Field(default_factory=dict)


class SecretEntryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    required: bool = True
    value_prefix: str = ""
    keyring: KeyringSourceModel | None = None
    setting: SettingSourceModel | None = None
    literal: LiteralSourceModel | None = None
    derived: DerivedSourceModel | None = None
    generator: GeneratorModel | None = None
    adopt_from: AdoptFromModel | None = None

    @model_validator(mode="after")
    def validate_one_source(self) -> Self:
        sources = [self.keyring, self.setting, self.literal, self.derived]
        if sum(1 for s in sources if s is not None) != 1:
            raise ValueError(
                "secret entry must specify exactly one of: keyring, setting, literal, derived"
            )
        return self


class SecretTableModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    namespace: str
    name: str
    stack: str
    restarts: list[WorkloadModel] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    change_note: str = ""
    secret_type: SecretType = "Opaque"
    gate_namespace: str | None = None
    entry: list[SecretEntryModel] = Field(
        default_factory=list, validation_alias=AliasChoices("entry", "entries")
    )


class ClusterSecretsFileModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    secret: list[SecretTableModel] = Field(
        default_factory=list, validation_alias=AliasChoices("secret", "secrets")
    )


_CLUSTER_SECRETS_ADAPTER: TypeAdapter[ClusterSecretsFileModel] = TypeAdapter(
    ClusterSecretsFileModel
)


def _build_plain_source(input_model: DerivedInputModel) -> PlainSource:
    if input_model.keyring is not None:
        return KeyringSource(input_model.keyring.key, input_model.keyring.option)
    if input_model.setting is not None:
        return SettingSource(input_model.setting.option)
    if input_model.literal is not None:
        return LiteralSource(input_model.literal.value)
    raise ValueError("derived input has no source")


def _build_secret_entry(entry: SecretEntryModel) -> SecretEntry:
    source: SecretSource
    if entry.keyring is not None:
        source = KeyringSource(entry.keyring.key, entry.keyring.option)
    elif entry.setting is not None:
        source = SettingSource(entry.setting.option)
    elif entry.literal is not None:
        source = LiteralSource(entry.literal.value)
    elif entry.derived is not None:
        inputs = {k: _build_plain_source(v) for k, v in entry.derived.inputs.items()}
        source = DerivedSource(entry.derived.template, inputs)
    else:
        raise ValueError("entry has no source")

    generator = (
        SecretGenerator(
            entry.generator.encoding,
            entry.generator.nbytes,
            prefix=entry.generator.prefix,
        )
        if entry.generator
        else None
    )
    adopt_from = (
        SecretKeyRef(
            entry.adopt_from.namespace,
            entry.adopt_from.name,
            entry.adopt_from.key,
        )
        if entry.adopt_from
        else None
    )
    return SecretEntry(
        key=entry.key,
        source=source,
        required=entry.required,
        generator=generator,
        adopt_from=adopt_from,
        value_prefix=entry.value_prefix,
    )


def _build_cluster_secret(table: SecretTableModel) -> ClusterSecret:
    restarts = tuple(Workload(w.kind, w.name) for w in table.restarts)
    entries = tuple(_build_secret_entry(e) for e in table.entry)
    return ClusterSecret(
        namespace=table.namespace,
        name=table.name,
        stack=table.stack,
        entries=entries,
        restarts=restarts,
        labels=table.labels,
        change_note=table.change_note,
        secret_type=table.secret_type,
        gate_namespace=table.gate_namespace,
    )


def load_cluster_secrets(path: Path) -> tuple[ClusterSecret, ...]:
    """Read a cluster-secrets.toml file and build existing ClusterSecret dataclasses."""
    with path.open("rb") as f:
        data = tomllib.load(f)
    validated = _CLUSTER_SECRETS_ADAPTER.validate_python(data)
    return tuple(_build_cluster_secret(table) for table in validated.secret)


_FIXTURE_SECRETS_FILE = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "cluster-secrets.toml"
)
_FALLBACK_FIXTURE_SECRETS_FILE = Path("tests/fixtures/cluster-secrets.toml")


def _resolve_fixture_secrets_file() -> Path | None:
    if _FIXTURE_SECRETS_FILE.is_file():
        return _FIXTURE_SECRETS_FILE
    if _FALLBACK_FIXTURE_SECRETS_FILE.is_file():
        return _FALLBACK_FIXTURE_SECRETS_FILE
    return None


def load_cluster_secrets_table(
    env: Any = None,
    *,
    k8s_dir: Path | None = None,
) -> tuple[ClusterSecret, ...]:
    """Load the full cluster secrets table: environment rows from cluster-secrets.toml and product rows."""
    if env is None and k8s_dir is None:
        try:
            from devops_cli.k8s.environment import resolve_environment

            env = resolve_environment(None)
        except ConfigurationError:
            env = None
    elif env is None and k8s_dir is not None:
        try:
            from devops_cli.k8s.environment import tree_at

            env = tree_at(k8s_dir)
        except ConfigurationError, OSError:
            env = None

    env_file: Path | None = None
    if env is not None:
        cluster_secrets_path = getattr(env, "cluster_secrets", None)
        if isinstance(cluster_secrets_path, Path) and cluster_secrets_path.is_file():
            env_file = cluster_secrets_path
    if env_file is None and k8s_dir is not None:
        direct = k8s_dir / "cluster-secrets.toml"
        if direct.is_file():
            env_file = direct
    if env_file is None:
        env_file = _resolve_fixture_secrets_file()

    env_rows = load_cluster_secrets(env_file) if env_file is not None else ()
    return (*env_rows, *CLUSTER_SECRETS)


CLUSTER_SECRETS: tuple[ClusterSecret, ...] = (
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
    # The bearer token of Crawl4AI, which refuses to listen beyond loopback without it (#3882).
    # The pod reads the token at start, so a change restarts it.
    ClusterSecret(
        namespace="devops",
        name="crawl4ai",
        stack="devops",
        entries=(
            SecretEntry(
                CRAWL4AI_ENV_NAME,
                _CRAWL4AI_TOKEN,
                generator=SecretGenerator("urlsafe", 32),
            ),
        ),
        restarts=(Workload("deployment", "crawl4ai"),),
        labels={"app.kubernetes.io/name": "crawl4ai"},
    ),
    # The server secret of SearXNG, which refuses to start with its default key (#3924). The pod
    # reads the secret at start, so a change restarts it.
    ClusterSecret(
        namespace="devops",
        name="searxng",
        stack="devops",
        entries=(
            SecretEntry(
                "SEARXNG_SECRET",
                KeyringSource(SEARXNG_SERVER_KEY),
                generator=SecretGenerator("hex", 32),
            ),
        ),
        restarts=(Workload("deployment", "searxng"),),
        labels={"app.kubernetes.io/name": "searxng"},
    ),
    # The basic-auth Secret of the OpenMetrics endpoint of SearXNG (#4201). The render-settings
    # init container writes its password into the rendered settings file, and the ServiceMonitor
    # sends both keys to the scrape, so a change restarts the pod that serves it. The metrics are
    # an optional feature: the pod starts without the password and turns the endpoint off, so a
    # push with no password skips it (#6805).
    ClusterSecret(
        namespace="devops",
        name="searxng-metrics-auth",
        stack="devops",
        secret_type=_BASIC_AUTH_SECRET_TYPE,
        entries=(
            SecretEntry("username", LiteralSource("searxng")),
            SecretEntry("password", KeyringSource(SEARXNG_METRICS_AUTH_KEY), required=False),
        ),
        restarts=(Workload("deployment", "searxng"),),
        labels={"app.kubernetes.io/name": "searxng"},
    ),
    # The bearer token of the MCP server, which refuses to start without it. The pod reads the
    # token at start, so a change restarts it. The server accepts one token, so the keys of the
    # stage and implement clients in Secret devops/devops-cli read the same keyring entry.
    ClusterSecret(
        namespace="devops",
        name="mcp-server",
        stack="devops",
        entries=(
            SecretEntry(
                MCP_SERVER_ENV_NAME,
                _MCP_TOKEN,
                generator=SecretGenerator("urlsafe", 32),
            ),
        ),
        restarts=(Workload("deployment", "mcp-server"),),
        labels={"app.kubernetes.io/name": "mcp-server"},
    ),
    # The GitHub App that self-hosted Renovate acts as (#4905). The keys are the variables of the
    # settings, so the token init container of CronJob `renovate` takes the Secret with `envFrom`
    # and `devops gh app-token --app renovate` reads it. Each run reads the Secret at its start,
    # so no workload restarts. A person types each value, so the push makes none. Renovate is an
    # optional feature: a push with no Renovate settings skips the keys and writes no Secret.
    ClusterSecret(
        namespace="devops",
        name="renovate",
        stack="devops",
        entries=(
            SecretEntry(
                "DEVOPS_CLI_RENOVATE_GITHUB_APP_ID",
                SettingSource("renovate.github_app_id"),
                required=False,
            ),
            SecretEntry(
                "DEVOPS_CLI_RENOVATE_GITHUB_APP_INSTALLATION_ID",
                SettingSource("renovate.github_app_installation_id"),
                required=False,
            ),
            SecretEntry(
                "DEVOPS_CLI_RENOVATE_GITHUB_APP_PRIVATE_KEY",
                KeyringSource.for_credential("renovate.github_app_private_key"),
                required=False,
            ),
        ),
        labels={"app.kubernetes.io/name": "renovate"},
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
            # The client of the roadmap Service sends the token of Secret devops/crawl4ai.
            SecretEntry(
                "DEVOPS_CLI_CRAWL4AI_API_TOKEN",
                _CRAWL4AI_TOKEN,
                required=False,
                adopt_from=SecretKeyRef("devops", "crawl4ai", CRAWL4AI_ENV_NAME),
            ),
            # The stage and implement jobs send the token of Secret devops/mcp-server to the role
            # endpoints of the MCP server.
            SecretEntry(
                "DEVOPS_CLI_MCP_STAGE_TOKEN",
                _MCP_TOKEN,
                required=False,
                adopt_from=SecretKeyRef("devops", "mcp-server", MCP_SERVER_ENV_NAME),
            ),
            SecretEntry(
                "DEVOPS_CLI_MCP_IMPLEMENT_TOKEN",
                _MCP_TOKEN,
                required=False,
                adopt_from=SecretKeyRef("devops", "mcp-server", MCP_SERVER_ENV_NAME),
            ),
            # A pod that loads this Secret with envFrom, such as a Job of CronJob devops-cli,
            # reads Qdrant with the read-only key, so it holds no write or delete path (#3823).
            # The runner pod and the roadmap Service do not hold the key (#6518).
            SecretEntry(
                "DEVOPS_CLI_QDRANT_API_KEY",
                KeyringSource.for_credential("qdrant.read_only_api_key"),
                generator=SecretGenerator("urlsafe", 32),
                adopt_from=SecretKeyRef("llm", "qdrant-api-key", "read-only-api-key"),
            ),
        ),
        restarts=(Workload("deployment", "roadmap-service"),),
        labels={"app.kubernetes.io/name": "devops-cli"},
    ),
    # The roadmap Service's own LiteLLM virtual key, with a budget and a requests-per-minute
    # limit (#3685). A person mints it on the gateway and stores it in the keyring; the entry is
    # optional because the gateway is up before the key exists.
    ClusterSecret(
        namespace="devops",
        name="roadmap-service-llm-key",
        stack="devops",
        entries=(
            SecretEntry(
                "api-key",
                KeyringSource.for_credential("roadmap_service.llm_key"),
                required=False,
            ),
        ),
        restarts=(Workload("deployment", "roadmap-service"),),
        labels={"app.kubernetes.io/name": "roadmap-service"},
    ),
    ClusterSecret(
        namespace="devops",
        name="qdrant-api-key",
        stack="devops",
        entries=(
            SecretEntry(
                "api-key",
                KeyringSource.for_credential("qdrant.api_key"),
                generator=SecretGenerator("urlsafe", 32),
                adopt_from=SecretKeyRef("llm", "qdrant-api-key", "api-key"),
            ),
        ),
        labels={"app.kubernetes.io/name": "rag-ingest"},
    ),
)

# The Secrets that serve an optional feature: a workload starts without one, and only that
# feature is unavailable. A pull request that adds a reference to one of these makes the reference
# optional, so a missing Secret never stops a required Service (#5200).
OPTIONAL_FEATURE_SECRETS: Final[tuple[str, ...]] = (
    "monitoring/grafana-image-renderer",
    "devops/renovate",
    "devops/searxng-metrics-auth",
)


def secret_names(table: Iterable[ClusterSecret] | None = None) -> list[str]:
    """Every `namespace/name` in the table, in its order."""
    if table is None:
        table = load_cluster_secrets_table()
    return [secret.ref for secret in table]


def secrets_for_stacks(
    stacks: Iterable[str], table: Iterable[ClusterSecret] | None = None
) -> tuple[ClusterSecret, ...]:
    """The rows of the given stacks, in table order."""
    if table is None:
        table = load_cluster_secrets_table()
    wanted = set(stacks)
    return tuple(secret for secret in table if secret.stack in wanted)


def secrets_by_ref(
    refs: Iterable[str], table: Iterable[ClusterSecret] | None = None
) -> tuple[tuple[ClusterSecret, ...], list[str]]:
    """The rows named `namespace/name`, in table order, and the names the table lacks."""
    if table is None:
        table = load_cluster_secrets_table()
    wanted = list(dict.fromkeys(refs))
    rows = tuple(table)
    known = {secret.ref for secret in rows}
    return tuple(secret for secret in rows if secret.ref in wanted), [
        ref for ref in wanted if ref not in known
    ]


def table_stacks(table: Iterable[ClusterSecret] | None = None) -> tuple[str, ...]:
    """The stacks the table's rows belong to, in table order."""
    if table is None:
        table = load_cluster_secrets_table()
    return tuple(dict.fromkeys(secret.stack for secret in table))


def keyring_sources(entry: SecretEntry) -> tuple[KeyringSource, ...]:
    """The keyring entries an entry reads: its own source, or the inputs of a derived one."""
    source = entry.source
    sources = source.inputs.values() if isinstance(source, DerivedSource) else (source,)
    return tuple(s for s in sources if isinstance(s, KeyringSource))


def generator_for_option(
    option: str, table: Iterable[ClusterSecret] | None = None
) -> SecretGenerator | None:
    """The generator the table declares for the managed credential `option`."""
    if table is None:
        table = load_cluster_secrets_table()
    return next(
        (
            entry.generator
            for secret in table
            for entry in secret.entries
            if entry.generator is not None
            and any(source.option == option for source in keyring_sources(entry))
        ),
        None,
    )


def generator_option_names(
    table: Iterable[ClusterSecret] | None = None,
) -> tuple[str, ...]:
    """The managed credential options whose row declares a generator, sorted."""
    if table is None:
        table = load_cluster_secrets_table()
    return tuple(
        sorted(
            {
                source.option
                for secret in table
                for entry in secret.entries
                if entry.generator is not None
                for source in keyring_sources(entry)
                if source.option is not None
            }
        )
    )


def keyring_only_keys(table: Iterable[ClusterSecret] | None = None) -> frozenset[str]:
    """The keyring keys the table declares that no Settings option reads."""
    if table is None:
        table = load_cluster_secrets_table()
    return frozenset(
        source.key
        for secret in table
        for entry in secret.entries
        for source in keyring_sources(entry)
        if source.option is None
    )


def _resolve_manifest_namespace(doc: Any, file_path: Path, root: Path) -> str:
    """Find the namespace of a document from its metadata, or from its path under k8s."""
    if isinstance(doc, dict):
        meta = doc.get("metadata")
        if isinstance(meta, dict):
            ns = meta.get("namespace")
            if isinstance(ns, str) and ns:
                return ns
    if root.is_dir() and file_path.is_relative_to(root):
        rel = file_path.relative_to(root)
        if len(rel.parts) > 1:
            return rel.parts[0]
    return file_path.parent.name


def _find_secret_key_refs(node: Any) -> list[tuple[str, str]]:
    """Return each (secret_name, key_name) referenced by a secretKeyRef in node."""
    refs: list[tuple[str, str]] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            skr = current.get("secretKeyRef")
            if isinstance(skr, dict):
                name = skr.get("name")
                key = skr.get("key")
                if isinstance(name, str) and isinstance(key, str):
                    refs.append((name, key))
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return refs


def _check_secret_ref(
    secret_name: str,
    key: str,
    doc_ns: str,
    table_by_ref: Mapping[str, ClusterSecret],
    table_by_name: Mapping[str, list[ClusterSecret]],
    file_path: Path,
) -> str | None:
    secret_ref = f"{doc_ns}/{secret_name}" if doc_ns else None
    matched_secret: ClusterSecret | None = None
    if secret_ref and secret_ref in table_by_ref:
        matched_secret = table_by_ref[secret_ref]
    elif not secret_ref and len(table_by_name.get(secret_name, ())) == 1:
        matched_secret = table_by_name[secret_name][0]

    if matched_secret is None:
        return None

    known_keys = {entry.key for entry in matched_secret.entries}
    if key not in known_keys:
        return f"{file_path}: Secret {matched_secret.ref} has no row for key {key!r}"
    return None


def check_secret_key_refs(
    k8s_dir: Path | str,
    table: Iterable[ClusterSecret] | None = None,
) -> list[str]:
    """Verify that every secretKeyRef in manifests or values under `k8s_dir` referencing a Secret
    in `table` names a key of that Secret's entries.

    Returns a list of findings for any unknown key referenced. Skips Secrets that are not in
    `table` (such as chart-made or operator-made Secrets).
    """
    root = Path(k8s_dir)
    if table is None:
        table = load_cluster_secrets_table()
    table_list = tuple(table)
    table_by_ref = {s.ref: s for s in table_list}
    table_by_name: dict[str, list[ClusterSecret]] = {}
    for s in table_list:
        table_by_name.setdefault(s.name, []).append(s)

    files = (
        [root]
        if root.is_file()
        else [p for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in (".yaml", ".yml")]
    )
    findings: list[str] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        documents = list(yaml.safe_load_all(content))

        for doc in documents:
            if not isinstance(doc, (dict, list)):
                continue
            doc_ns = _resolve_manifest_namespace(doc, file_path, root)
            for secret_name, key in _find_secret_key_refs(doc):
                problem = _check_secret_ref(
                    secret_name, key, doc_ns, table_by_ref, table_by_name, file_path
                )
                if problem:
                    findings.append(problem)
    return findings
