"""The Secrets a cluster's stacks read, and where each of their values comes from.

One table, held as data, is the single list of what a cluster needs: `devops k8s push-secrets`
and `devops k8s deploy-stack` write every row from the workstation's keyring, and a gate test
fails on any Secret a manifest or values file under k8s/ references without a row. Each row
lands with the item that adds the Secret's consumer.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from devops_cli.config import options as opt

MANAGED_BY_LABEL = "app.kubernetes.io/managed-by"
MANAGED_BY_VALUE = "devops-cli"
FIELD_MANAGER = "devops-cli"

# Rows of `base` belong to the root kustomization, which every deploy-stack run applies.
BASE_STACK = "base"
# Stacks deploy-stack never deploys. Their rows are pushed wherever their namespace exists.
DETACHED_STACKS: tuple[str, ...] = ("devops",)

# Generated values nobody types live under keyring-only keys; no Settings option reads them.
LLM_GATEWAY_MASTER_KEY = "llm_gateway_master_key"
# LiteLLM refuses a master key without this prefix.
LITELLM_KEY_PREFIX = "sk-"


@dataclass(frozen=True)
class KeyringSource:
    """A keyring entry. `option` names the managed credential it backs; None for keyring-only."""

    key: str
    option: str | None = None

    @property
    def label(self) -> str:
        """How output names the source, never its value."""
        return f"keyring {self.key}"


@dataclass(frozen=True)
class GitHubAccountSource:
    """The token gh keeps in the OS keyring for the machine account (`k8s.github_account`)."""

    @property
    def label(self) -> str:
        """How output names the source."""
        return "gh account"


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


SecretSource = KeyringSource | GitHubAccountSource | SettingSource | LiteralSource


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
    optional one is skipped. Every value must start with `value_prefix`.
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
    """A Secret the cluster needs, the stack it belongs to and the workloads that read it."""

    namespace: str
    name: str
    stack: str
    entries: tuple[SecretEntry, ...]
    restarts: tuple[Workload, ...] = ()
    labels: dict[str, str] = field(default_factory=dict)
    change_note: str = ""

    @property
    def ref(self) -> str:
        """`namespace/name`."""
        return f"{self.namespace}/{self.name}"

    def manifest_labels(self) -> dict[str, str]:
        """The labels every pushed Secret carries, with its own."""
        return {**self.labels, MANAGED_BY_LABEL: MANAGED_BY_VALUE}


_LLM_GATEWAY_KEY = KeyringSource(LLM_GATEWAY_MASTER_KEY)

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
        ),
        restarts=(Workload("deployment", "llm-gateway"),),
        labels={"app.kubernetes.io/name": "llm-gateway"},
        change_note=(
            "Open WebUI keeps the gateway connection stored in its database: update the key "
            "under Admin Panel > Settings > Connections."
        ),
    ),
    ClusterSecret(
        namespace="llm",
        name="qdrant-api-key",
        stack="llm",
        entries=(
            SecretEntry(
                "api-key",
                KeyringSource("qdrant_api_key", opt.QDRANT_API_KEY),
                generator=SecretGenerator("urlsafe", 32),
            ),
        ),
        restarts=(Workload("statefulset", "qdrant"),),
        labels={"app.kubernetes.io/name": "qdrant"},
    ),
    ClusterSecret(
        namespace="llm",
        name="valkey-runs-auth",
        stack="llm",
        entries=(
            SecretEntry(
                "password",
                KeyringSource("runs_index_password", opt.RUNS_INDEX_PASSWORD),
                generator=SecretGenerator("hex", 32),
            ),
        ),
        restarts=(Workload("deployment", "valkey-runs"),),
        labels={"app.kubernetes.io/name": "valkey-runs"},
    ),
    ClusterSecret(
        namespace="cloudflared",
        name="cloudflared-token",
        stack=BASE_STACK,
        entries=(
            SecretEntry(
                "token",
                KeyringSource("cloudflare_tunnel_token", opt.CLOUDFLARE_TUNNEL_TOKEN),
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
            SecretEntry("GH_TOKEN", GitHubAccountSource()),
            SecretEntry(
                "DEVOPS_CLI_AI_API_KEY",
                _LLM_GATEWAY_KEY,
                adopt_from=SecretKeyRef("llm", "llm-gateway-secrets", "master-key"),
                value_prefix=LITELLM_KEY_PREFIX,
            ),
            SecretEntry(
                "DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS",
                KeyringSource("service_webhook_secrets", opt.SERVICE_WEBHOOK_SECRETS),
                required=False,
            ),
            SecretEntry(
                "DEVOPS_CLI_TAVILY_API_KEY",
                KeyringSource("tavily_api_key", opt.TAVILY_API_KEY),
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
                KeyringSource("grafana_password", opt.GRAFANA_PASSWORD),
                generator=SecretGenerator("urlsafe", 32),
                adopt_from=SecretKeyRef("monitoring", "grafana", "admin-password"),
            ),
        ),
        restarts=(Workload("deployment", "grafana"),),
        labels={"app.kubernetes.io/name": "grafana"},
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


def keyring_only_keys(table: Iterable[ClusterSecret] = CLUSTER_SECRETS) -> frozenset[str]:
    """The keyring keys the table declares that no Settings option reads."""
    return frozenset(
        entry.source.key
        for secret in table
        for entry in secret.entries
        if isinstance(entry.source, KeyringSource) and entry.source.option is None
    )
