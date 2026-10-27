"""Configuration settings resolution, Pydantic models, and keyring helpers."""

from __future__ import annotations

import copy
import json
import logging
import operator
import os
import threading
import time
import types
import typing
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Any

import httpx2
import yaml
from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

import devops_cli.config.options as opt
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_KEYRING_UNLOCK_PROBE_KEY,
    CONST_SETTINGS_CACHE_SETTLE_SECONDS,
)
from devops_cli.config.constants import (
    CONST_CONFIG_PATH as CONFIG_PATH,
)
from devops_cli.config.constants import (
    CONST_KEYRING_SERVICE as KEYRING_SERVICE,
)
from devops_cli.config.constants import (
    CONST_PROJECT_CONFIG_CANDIDATES as PROJECT_CONFIG_CANDIDATES,
)
from devops_cli.config.constants import (
    CONST_PROJECT_CONFIG_ENV as PROJECT_CONFIG_ENV,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_CONTEXT_WINDOW,
    DEFAULT_AI_GATEWAY_ENABLED,
    DEFAULT_AI_GATEWAY_PROVIDER,
    DEFAULT_AI_HARDWARE_COST_USD,
    DEFAULT_AI_MAX_RETRIES,
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROVIDER,
    DEFAULT_AI_REASONING_EFFORT,
    DEFAULT_AI_REFERENCE_EMBEDDING_MODEL,
    DEFAULT_AI_REFERENCE_MODEL,
    DEFAULT_AI_REFERENCE_PROVIDER,
    DEFAULT_AI_SUPPORTS_REASONING,
    DEFAULT_AI_TEMPERATURE,
    DEFAULT_AI_TOP_P,
    DEFAULT_ANALYSIS_DATA_DIR,
    DEFAULT_AUDIT_LOG_PATH,
    DEFAULT_BENCHMARKS_DATA_DIR,
    DEFAULT_CACHE_DATA_DIR,
    DEFAULT_DATA_DIR,
    DEFAULT_FEEDBACK_DATASET_PATH,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_LLM_CACHE_ENABLED,
    DEFAULT_LLM_CACHE_MAX_ENTRIES,
    DEFAULT_LLM_CACHE_TTL_SECONDS,
    DEFAULT_LOGS_DATA_DIR,
    DEFAULT_MODELS_DATA_DIR,
    DEFAULT_OLLAMA_MAX_PARALLEL,
    DEFAULT_OTEL_ENDPOINT,
    DEFAULT_QDRANT_TIMEOUT_SECONDS,
    DEFAULT_RAG_CHUNK_OVERLAP,
    DEFAULT_RAG_CHUNK_SIZE,
    DEFAULT_RAG_DATA_DIR,
    DEFAULT_RAG_EMBEDDING_MODEL,
    DEFAULT_RAG_SCORE_THRESHOLD,
    DEFAULT_RAG_TOP_K,
    DEFAULT_REPOS_BASE_DIR,
    DEFAULT_REVIEW_TIMEOUT_SECONDS,
    DEFAULT_REVIEWS_DATA_DIR,
    DEFAULT_RUNS_DATA_DIR,
    DEFAULT_SAMPLES_DATA_DIR,
    DEFAULT_SANDBOX_EXCLUDE_HOME,
    DEFAULT_SERVICE_DRAIN_TIMEOUT_SECONDS,
    DEFAULT_SERVICE_GITHUB_REQUESTS_PER_HOUR,
    DEFAULT_SERVICE_POLL_INTERVAL_SECONDS,
    DEFAULT_SSH_KEY_DIR,
    DEFAULT_SSH_KEY_PREFIX,
    DEFAULT_SSH_ROTATION_DAYS,
    DEFAULT_THREAT_INTEL_CACHE_TTL_SECONDS,
    DEFAULT_TLS_DATA_DIR,
    DEFAULT_VALKEY_TIMEOUT_SECONDS,
    DEFAULT_VALKEY_URL,
    DEFAULT_WORKSPACE_FILE,
)
from devops_cli.config.env import ENV_OTEL_EXPORTER_OTLP_ENDPOINT, OPTION_TO_ENV_VAR
from devops_cli.core.dns_names import OptionalConfiguredDomain
from devops_cli.core.untrusted_trees import reads_untrusted_trees
from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import ERRORS
from devops_cli.valkey.endpoint import ValkeyEndpoint, parse_valkey_url

if typing.TYPE_CHECKING:
    from devops_cli.models.config import ConfigKeyRemoval

logger = logging.getLogger(__name__)

_SECRET_FIELDS: frozenset[str] = opt.SECRET_CONFIG_OPTIONS
_KEYRING_KEYS: dict[str, str] = opt.KEYRING_KEYS
# The options that still decide telemetry when the rest of the settings cannot load (#956).
_TELEMETRY_ENV_OPTIONS: tuple[str, ...] = (opt.TELEMETRY_ENABLED, opt.TELEMETRY_ENDPOINT)


class SecretStorageError(RuntimeError):
    """Raised when a secret cannot be stored in the configured keyring backend."""


class KeyringLockedError(SecretStorageError):
    """Raised when the keyring exists but is locked, so nothing can be stored until unlocked."""


class KeyringUnavailableError(SecretStorageError):
    """Raised when secrets would land in no persistent, encrypted keyring.

    That is no backend, an unencrypted one, or the in-memory store `DEVOPS_CLI_HEADLESS_AUTH`
    selects, which loses every value when the process exits.
    """


_KEYRING_LOCKED_HINT = "the OS keyring is locked; run `devops devcontainer unlock-keyring`"


def _is_unencrypted_backend(backend: object) -> bool:
    """Report whether a backend keeps secrets in plain text."""
    return "Plaintext" in type(backend).__name__ or "keyrings.alt" in type(backend).__module__


def _ensure_keyring_backend() -> bool:
    """Ensure keyring has a usable, encrypted backend and reject unencrypted backends."""
    import keyring
    from keyring.backends.chainer import ChainerBackend
    from keyring.backends.fail import Keyring as FailKeyring

    backend = keyring.get_keyring()
    if backend is None or isinstance(backend, FailKeyring):
        return False

    # keyring picks the chainer whenever several backends are viable, and the chainer falls
    # through to the next one when a write fails -- a locked Secret Service would hand the
    # secret to any plaintext backend behind it. Every backend it chains must be encrypted.
    members = list(backend.backends) if isinstance(backend, ChainerBackend) else [backend]
    if not members or any(_is_unencrypted_backend(member) for member in members):
        return False

    priority = getattr(backend, "priority", 0)
    return bool(priority > 0)


_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


def _validate_http_url(v: str) -> str:
    """Validate HTTP(S) URL preserving exact string representation and checking httpx2 origin."""
    parsed = _HTTP_URL_ADAPTER.validate_python(v)
    try:
        raw_url = httpx2.URL(v)
        parsed_url = httpx2.URL(str(parsed))
        if raw_url.origin != parsed_url.origin:
            raise ValueError("httpx2 would send this URL to a different host or port")
    except httpx2.InvalidURL as exc:
        raise ValueError("httpx2 cannot parse this URL") from exc
    return v


def _validate_service_url(v: str) -> str:
    """Validate cluster service URL (k8s://, k8s+https://) or HTTP(S) URL."""
    from devops_cli.k8s.service_proxy import ServiceAddressError, is_service_url, parse_service_url

    if is_service_url(v):
        try:
            parse_service_url(v)
        except ServiceAddressError as exc:
            raise ValueError(str(exc)) from exc
        return v
    return _validate_http_url(v)


HttpUrlStr = Annotated[
    str, StringConstraints(strip_whitespace=True), AfterValidator(_validate_http_url)
]
ServiceUrlStr = Annotated[
    str, StringConstraints(strip_whitespace=True), AfterValidator(_validate_service_url)
]


def _is_list_annotation(annotation: Any) -> bool:
    """Report whether annotation represents a list or optional list type."""
    origin = typing.get_origin(annotation)
    if origin is list:
        return True
    if origin in (typing.Union, types.UnionType):
        return any(typing.get_origin(arg) is list for arg in typing.get_args(annotation))
    return False


def _validation_error_key(exc: ValidationError, prefix: tuple[str, ...] = ()) -> str:
    """Extract the dotted key for the first validation error."""
    errors = exc.errors(include_url=False, include_input=False)
    if not errors:
        return ""
    loc = prefix + tuple(str(p) for p in errors[0].get("loc", ()))
    return ".".join(loc)


def _format_validation_error(exc: ValidationError, prefix: tuple[str, ...] = ()) -> str:
    """Format the first validation error as '<dotted.key>: <reason>'."""
    errors = exc.errors(include_url=False, include_input=False)
    if not errors:
        return str(exc)
    first = errors[0]
    loc = prefix + tuple(str(p) for p in first.get("loc", ()))
    msg = first.get("msg", "invalid value")
    if msg.startswith("Value error, "):
        msg = msg[len("Value error, ") :]
    key_str = ".".join(loc)
    return f"{key_str}: {msg}" if key_str else msg


class GitHubConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    default_org: str | None = None


class SSHConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    key_dir: Path = DEFAULT_SSH_KEY_DIR
    key_prefix: str | None = DEFAULT_SSH_KEY_PREFIX
    rotation_days: int = Field(default=DEFAULT_SSH_ROTATION_DAYS, gt=0)


class ReposConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    base_dir: Path = DEFAULT_REPOS_BASE_DIR


class WorkspaceConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    file: Path = DEFAULT_WORKSPACE_FILE


class GrafanaConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: ServiceUrlStr | None = None


class PrometheusConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: ServiceUrlStr | None = None


class ArgoCDConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: ServiceUrlStr | None = None


class QdrantConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: ServiceUrlStr | None = None
    collection_prefix: str = "devops"
    api_key: str | None = None
    timeout: float = Field(
        default=DEFAULT_QDRANT_TIMEOUT_SECONDS,
        gt=0,
        allow_inf_nan=False,
        description=(
            "Seconds each Qdrant request waits per attempt: RAG searches, and indexing's "
            "upserts and deletes, which share the client"
        ),
    )


class OpenWebUIConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: ServiceUrlStr | None = None


class RunsConfig(BaseModel):
    """The evaluation run store's shared index; records stay in `data.runs_dir` without it."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)

    # A Valkey URL such as `valkey://<host>:<port>/<db>`, checked as `valkey.url` is when the index
    # connects; unset keeps runs on this workstation only.
    index_url: str | None = None


class ValkeyConfig(BaseModel):
    """The Valkey that the caches, the dashboard and `devops valkey` use.

    `url` is checked when a client reads `endpoint`, not when the settings load, so a URL that is
    not valid stops only the Valkey commands. A file that still holds the removed `host`, `port`
    and `db` keys loads, and the next save drops them.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: str | None = Field(
        default=DEFAULT_VALKEY_URL,
        description=(
            "The Valkey endpoint, such as `valkeys://example.com:6380/0`: the scheme, the host, the "
            "port and the database. The scheme `valkeys` connects over TLS and checks the "
            "certificate against the host. The scheme `valkey` connects in plaintext. The URL holds "
            "no password: `valkey.password` is in the OS keyring"
        ),
    )
    password: str | None = None
    timeout: float = Field(default=DEFAULT_VALKEY_TIMEOUT_SECONDS, gt=0, allow_inf_nan=False)
    threat_intel_ttl: int = Field(default=DEFAULT_THREAT_INTEL_CACHE_TTL_SECONDS, gt=0)

    @property
    def endpoint(self) -> ValkeyEndpoint:
        """The endpoint of `url`, or of the default URL when `url` is unset or empty.

        A URL that is not valid raises `ConfigurationError` naming `valkey.url`.
        """
        return parse_valkey_url(
            self.url or DEFAULT_VALKEY_URL,
            setting=opt.VALKEY_URL,
            written_by=f"`devops k8s configure-urls` or `devops config set {opt.VALKEY_URL}`",
        )


class TempoConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: ServiceUrlStr | None = None


class PyroscopeConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: ServiceUrlStr | None = None


class TelemetryConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    enabled: bool = Field(default=True, description="Export OpenTelemetry traces and metrics")
    # Unset rather than the built-in endpoint, so OpenTelemetry's own variable can name the
    # collector when devops-cli's configuration does not.
    endpoint: HttpUrlStr | None = Field(
        default=None,
        description="OpenTelemetry collector that traces and metrics go to; unset, "
        f"`{ENV_OTEL_EXPORTER_OTLP_ENDPOINT}` names it, else `{DEFAULT_OTEL_ENDPOINT}`",
    )
    # Opt-In in the OpenTelemetry semantic conventions: `devops uv run` and `devops gh api` pass
    # the arguments of a person on, and the secret mask does not find every credential (#2025).
    capture_command_args: bool = Field(
        default=False,
        description="Record the arguments of each program that devops-cli runs in "
        "`process.command_args` on its subprocess span, each argument through the secret mask. "
        "Off by default: an argument can be a credential that the mask does not find",
    )
    capture_llm_content: bool = Field(
        default=False,
        description="Record LLM prompt and reply text in OpenTelemetry and Logfire telemetry spans. "
        "Off by default to prevent exposure of sensitive data",
    )
    logfire: bool = False
    logfire_token: str | None = None
    logfire_send_to_logfire: bool | str = "if-token-present"


class CIConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    gate_slots: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Number of CPU-heavy devops ci gates that run at once on this host "
            "(default: one for each 16 CPUs)"
        ),
    )


class SandboxConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    exclude_home_dir: bool = Field(
        default=DEFAULT_SANDBOX_EXCLUDE_HOME,
        description="Exclude user home directory entirely from sandbox access (/home/**/* and ~/**/*)",
    )


class KubernetesConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    context: str = Field(
        default="minikube",
        description="Active Kubernetes cluster context name (e.g. minikube, docker-desktop, kind-cluster, or cloud context)",
    )
    domain: OptionalConfiguredDomain = Field(
        default=None,
        description="Base domain name for homelab ingress routes and tunnel services (e.g. example.com)",
    )
    addressing: str | None = Field(
        default=None,
        description="Default addressing mode for cluster services: nodeport, proxy, or fqdn.",
    )
    github_account: str | None = Field(
        default=None,
        description=(
            "Login of the machine account whose gh token `devops k8s push-secrets` writes to the "
            "cluster as GH_TOKEN; `--github-account` overrides it"
        ),
    )


class CloudflareAccessConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    enabled: bool = Field(
        default=False,
        description="Whether Cloudflare Zero Trust Access protection is enabled",
    )
    allowed_emails: list[str] = Field(
        default_factory=list,
        description="List of email addresses permitted to authenticate through Cloudflare Access",
    )
    idp: str = Field(
        default="google",
        description="Identity provider name (e.g. google, one_time_pin)",
    )
    bypass_ips: list[str] = Field(
        default_factory=list,
        description="List of public IP addresses or CIDR blocks permitted to bypass Cloudflare Access authentication",
    )
    public_ip_bypass: str | None = Field(
        default=None,
        description="Homelab public IP address or CIDR block permitted to bypass Cloudflare Access authentication",
    )


class CloudflareConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    domain: OptionalConfiguredDomain = Field(
        default=None,
        description="Root or zone domain name managed in Cloudflare (e.g. example.com)",
    )
    tunnel: str | None = Field(
        default=None,
        description="Cloudflare tunnel name or identifier (e.g. homelab)",
    )
    account_id: str | None = Field(
        default=None,
        description="Cloudflare Account ID",
    )
    zone_id: str | None = Field(
        default=None,
        description="Cloudflare Zone ID",
    )
    public_ip_bypass: str | None = Field(
        default=None,
        description="Homelab public IP address or CIDR block permitted to bypass Cloudflare Access authentication",
    )
    access: CloudflareAccessConfig = Field(
        default_factory=CloudflareAccessConfig,
        description="Cloudflare Zero Trust Access application and policy configuration",
    )


class AIRAGConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)
    enabled: bool = True
    top_k: int = Field(default=DEFAULT_RAG_TOP_K, gt=0)
    score_threshold: float = Field(
        default=DEFAULT_RAG_SCORE_THRESHOLD, ge=0.0, le=1.0, allow_inf_nan=False
    )
    chunk_size: int = Field(default=DEFAULT_RAG_CHUNK_SIZE, gt=0)
    chunk_overlap: int = Field(default=DEFAULT_RAG_CHUNK_OVERLAP, ge=0)


class AICacheConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    enabled: bool = DEFAULT_LLM_CACHE_ENABLED
    ttl_seconds: int = Field(default=DEFAULT_LLM_CACHE_TTL_SECONDS, gt=0)
    max_entries: int = Field(default=DEFAULT_LLM_CACHE_MAX_ENTRIES, gt=0)
    append_cache: bool = False


class AITaskOverride(BaseModel):
    """Per-task model/server override; unset fields fall back to the parent AIConfig."""

    model_config = ConfigDict(
        extra="forbid", frozen=False, validate_assignment=True, hide_input_in_errors=True
    )
    provider: str | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    supports_reasoning: bool | None = None
    use_model_sampling: bool | None = Field(
        default=None,
        description="Leave sampling parameters to the model. When true, requests carry neither temperature nor top_p.",
    )
    temperature: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    context_window: int | None = Field(default=None, gt=0)
    num_ctx: int | None = Field(default=None, gt=0)
    max_tokens: int | None = Field(default=None, gt=0)
    ollama_urls: list[HttpUrlStr] | None = None
    ollama_max_parallel: int | None = Field(default=None, gt=0)
    api_base_url: HttpUrlStr | None = None
    max_retries: int | None = Field(default=None, ge=0)
    timeout: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
        description=(
            "Seconds this task's requests wait for the next data of their reply, in place of "
            "`ai.timeout`"
        ),
    )


class AITasksConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=False, validate_assignment=True, hide_input_in_errors=True
    )
    chat: AITaskOverride = AITaskOverride()
    metadata: AITaskOverride = AITaskOverride()
    analysis: AITaskOverride = AITaskOverride()
    verification: AITaskOverride = AITaskOverride()
    compose: AITaskOverride = AITaskOverride()
    embedding: AITaskOverride = Field(
        default_factory=lambda: AITaskOverride(model=DEFAULT_RAG_EMBEDDING_MODEL)
    )


class AIConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=False, validate_assignment=True, hide_input_in_errors=True
    )
    provider: str = DEFAULT_AI_PROVIDER  # ollama | claude | copilot | openai
    model: str = DEFAULT_AI_MODEL
    api_key: str | None = Field(default=None, repr=False)
    reference_model: str = DEFAULT_AI_REFERENCE_MODEL
    reference_embedding_model: str = DEFAULT_AI_REFERENCE_EMBEDDING_MODEL
    reference_provider: str = DEFAULT_AI_REFERENCE_PROVIDER
    hardware_cost_usd: float = Field(
        default=DEFAULT_AI_HARDWARE_COST_USD, ge=0.0, allow_inf_nan=False
    )
    reasoning_effort: str | None = DEFAULT_AI_REASONING_EFFORT
    supports_reasoning: bool = DEFAULT_AI_SUPPORTS_REASONING
    use_model_sampling: bool = Field(
        default=False,
        description="Leave sampling parameters to the model. When true, requests carry neither temperature nor top_p.",
    )
    temperature: float = Field(default=DEFAULT_AI_TEMPERATURE, ge=0.0, allow_inf_nan=False)
    top_p: float = Field(default=DEFAULT_AI_TOP_P, ge=0.0, le=1.0, allow_inf_nan=False)
    context_window: int = Field(default=DEFAULT_AI_CONTEXT_WINDOW, gt=0)
    num_ctx: int | None = Field(default=None, gt=0)
    max_tokens: int | None = Field(default=None, gt=0)
    ollama_urls: list[HttpUrlStr] = Field(default_factory=list)
    ollama_max_parallel: int = Field(default=DEFAULT_OLLAMA_MAX_PARALLEL, gt=0)
    gateway_provider: str = DEFAULT_AI_GATEWAY_PROVIDER
    gateway_url: HttpUrlStr | None = None
    gateway_enabled: bool = DEFAULT_AI_GATEWAY_ENABLED
    gateway_weights: dict[str, int] = Field(default_factory=dict)
    gateway_concurrency: dict[str, int] = Field(default_factory=dict)
    portkey_url: HttpUrlStr | None = None
    api_base_url: HttpUrlStr | None = None
    allow_private_network: bool = False
    max_retries: int = Field(default=DEFAULT_AI_MAX_RETRIES, ge=0)
    timeout: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
        description=(
            "Seconds each LLM request waits for the next data of its reply: a streamed reply, "
            "such as every OpenAI-compatible chat reply, can take longer in total. "
            "`ai.tasks.<task>.timeout` sets one task's. Unset, a request waits "
            f"{DEFAULT_HTTP_TIMEOUT_SECONDS:g} s, and a review's analysis requests "
            f"{DEFAULT_REVIEW_TIMEOUT_SECONDS:g} s"
        ),
    )
    tasks: AITasksConfig = AITasksConfig()
    rag: AIRAGConfig = AIRAGConfig()
    cache: AICacheConfig = AICacheConfig()
    task_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_append_cache(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data.pop("durable", None)
            if "ollama_base_url" in data:
                val = data.pop("ollama_base_url")
                if "ollama_urls" not in data and val:
                    data["ollama_urls"] = [val] if isinstance(val, str) else val
            if "append_cache" in data:
                val = data.pop("append_cache")
                if "cache" in data and isinstance(data["cache"], dict):
                    data["cache"].setdefault("append_cache", val)
                elif "cache" not in data:
                    data["cache"] = {"append_cache": val}
        return data

    @property
    def append_cache(self) -> bool:
        """Convenience property delegating to self.cache.append_cache."""
        return self.cache.append_cache

    @append_cache.setter
    def append_cache(self, value: bool) -> None:
        self.cache.append_cache = value

    @property
    def get_ollama_urls(self) -> list[str]:
        """Return non-empty list of Ollama base URLs."""
        if not self.ollama_urls:
            return []

        from urllib.parse import urlsplit, urlunsplit

        from devops_cli.exceptions.config import ConfigurationError

        cleaned: list[str] = []
        for u in self.ollama_urls:
            raw = (u or "").strip().rstrip("/")
            if not raw:
                continue
            parts = urlsplit(raw)
            scheme = parts.scheme.lower()
            if scheme not in ("http", "https") or not parts.netloc or not parts.hostname:
                raise ConfigurationError(
                    f"Invalid ai.ollama_urls entry '{u}': must have http or https scheme and host",
                    key="ai.ollama_urls",
                )
            cleaned.append(
                urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment)).rstrip(
                    "/"
                )
            )
        return cleaned

    def for_task(self, task: str) -> AIConfig:
        """Return a copy with task-specific overrides from ai.tasks.<task> applied."""
        override: AITaskOverride = getattr(self.tasks, task, AITaskOverride())
        updates = {
            k: v
            for k, v in {
                "provider": override.provider,
                "model": override.model,
                "reasoning_effort": override.reasoning_effort,
                "supports_reasoning": override.supports_reasoning,
                "use_model_sampling": override.use_model_sampling,
                "temperature": override.temperature,
                "top_p": override.top_p,
                "context_window": override.context_window,
                "num_ctx": override.num_ctx,
                "max_tokens": override.max_tokens,
                "ollama_urls": override.ollama_urls,
                "ollama_max_parallel": override.ollama_max_parallel,
                "max_retries": override.max_retries,
                "timeout": override.timeout,
            }.items()
            if v is not None
        } | self._task_endpoint_updates(override)
        if task in AITasksConfig.model_fields:
            updates["task_name"] = task
        else:
            updates["task_name"] = None
        return self.model_copy(update=updates) if updates else self

    def _task_endpoint_updates(self, override: AITaskOverride) -> dict[str, str | None]:
        """Resolve a task's endpoints so no request reaches a base URL set for another provider.

        A task's own api_base_url applies to its provider; on a gateway task it is that task's
        gateway address. The global api_base_url carries over only to tasks that keep the global
        provider.
        """
        provider = override.provider or self.provider
        updates: dict[str, str | None] = {}
        if override.api_base_url:
            key = "gateway_url" if provider == CONST_AI_GATEWAY_PROVIDER else "api_base_url"
            updates[key] = override.api_base_url
        if provider != self.provider and "api_base_url" not in updates:
            updates["api_base_url"] = None
        return updates


_DEFAULT_CHILD_DATA_PATHS: tuple[tuple[str, Path, Path], ...] = (
    ("analysis_dir", DEFAULT_ANALYSIS_DATA_DIR, Path("analysis")),
    ("reviews_dir", DEFAULT_REVIEWS_DATA_DIR, Path("reviews")),
    ("logs_dir", DEFAULT_LOGS_DATA_DIR, Path("logs")),
    ("models_dir", DEFAULT_MODELS_DATA_DIR, Path("models")),
    ("cache_dir", DEFAULT_CACHE_DATA_DIR, Path("cache")),
    ("benchmarks_dir", DEFAULT_BENCHMARKS_DATA_DIR, Path("benchmarks")),
    ("rag_dir", DEFAULT_RAG_DATA_DIR, Path("rag")),
    ("samples_dir", DEFAULT_SAMPLES_DATA_DIR, Path("samples")),
    ("runs_dir", DEFAULT_RUNS_DATA_DIR, Path("runs")),
    ("tls_dir", DEFAULT_TLS_DATA_DIR, Path("tls")),
    ("audit_log_path", DEFAULT_AUDIT_LOG_PATH, Path("logs/audit.jsonl")),
    ("feedback_dataset_path", DEFAULT_FEEDBACK_DATASET_PATH, Path("feedback_dataset.jsonl")),
)

_CHILD_DATA_ENV_MAP: dict[str, str] = {
    "analysis_dir": "DEVOPS_CLI_DATA_ANALYSIS_DIR",
    "reviews_dir": "DEVOPS_CLI_DATA_REVIEWS_DIR",
    "logs_dir": "DEVOPS_CLI_DATA_LOGS_DIR",
    "models_dir": "DEVOPS_CLI_DATA_MODELS_DIR",
    "cache_dir": "DEVOPS_CLI_DATA_CACHE_DIR",
    "benchmarks_dir": "DEVOPS_CLI_DATA_BENCHMARKS_DIR",
    "rag_dir": "DEVOPS_CLI_DATA_RAG_DIR",
    "samples_dir": "DEVOPS_CLI_DATA_SAMPLES_DIR",
    "runs_dir": "DEVOPS_CLI_DATA_RUNS_DIR",
    "tls_dir": "DEVOPS_CLI_DATA_TLS_DIR",
    "audit_log_path": "DEVOPS_CLI_DATA_AUDIT_LOG_PATH",
    "feedback_dataset_path": "DEVOPS_CLI_DATA_FEEDBACK_DATASET_PATH",
}

_DEFAULT_CHILD_DATA_MAP: dict[str, Path] = {
    "analysis_dir": DEFAULT_ANALYSIS_DATA_DIR,
    "reviews_dir": DEFAULT_REVIEWS_DATA_DIR,
    "logs_dir": DEFAULT_LOGS_DATA_DIR,
    "models_dir": DEFAULT_MODELS_DATA_DIR,
    "cache_dir": DEFAULT_CACHE_DATA_DIR,
    "benchmarks_dir": DEFAULT_BENCHMARKS_DATA_DIR,
    "rag_dir": DEFAULT_RAG_DATA_DIR,
    "samples_dir": DEFAULT_SAMPLES_DATA_DIR,
    "runs_dir": DEFAULT_RUNS_DATA_DIR,
    "tls_dir": DEFAULT_TLS_DATA_DIR,
    "audit_log_path": DEFAULT_AUDIT_LOG_PATH,
    "feedback_dataset_path": DEFAULT_FEEDBACK_DATASET_PATH,
}


class ServiceConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)

    repos: list[str] = Field(default_factory=list)
    machine_account: str | None = None
    poll_interval_seconds: int = Field(default=DEFAULT_SERVICE_POLL_INTERVAL_SECONDS, ge=60)
    drain_timeout_seconds: int = Field(default=DEFAULT_SERVICE_DRAIN_TIMEOUT_SECONDS, gt=0)
    github_requests_per_hour: int = Field(default=DEFAULT_SERVICE_GITHUB_REQUESTS_PER_HOUR, gt=0)

    @field_validator("repos", mode="before")
    @classmethod
    def _parse_repos(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            trimmed = v.strip()
            if not trimmed:
                return []
            if trimmed.startswith("[") and trimmed.endswith("]"):
                try:
                    parsed = json.loads(trimmed)
                    if isinstance(parsed, list):
                        return [str(item) for item in parsed if item]
                except json.JSONDecodeError:
                    pass
            return [part.strip() for part in trimmed.split(",") if part.strip()]
        if isinstance(v, list):
            if (
                len(v) == 1
                and isinstance(v[0], str)
                and v[0].startswith("[")
                and v[0].endswith("]")
            ):
                try:
                    parsed = json.loads(v[0])
                    if isinstance(parsed, list):
                        return [str(item) for item in parsed if item]
                except Exception:
                    pass
            return [str(item) for item in v if item]
        return []


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)

    dir: Path = Field(default_factory=lambda: DEFAULT_DATA_DIR)
    analysis_dir: Path = Field(default_factory=lambda: DEFAULT_ANALYSIS_DATA_DIR)
    reviews_dir: Path = Field(default_factory=lambda: DEFAULT_REVIEWS_DATA_DIR)
    logs_dir: Path = Field(default_factory=lambda: DEFAULT_LOGS_DATA_DIR)
    models_dir: Path = Field(default_factory=lambda: DEFAULT_MODELS_DATA_DIR)
    cache_dir: Path = Field(default_factory=lambda: DEFAULT_CACHE_DATA_DIR)
    benchmarks_dir: Path = Field(default_factory=lambda: DEFAULT_BENCHMARKS_DATA_DIR)
    rag_dir: Path = Field(default_factory=lambda: DEFAULT_RAG_DATA_DIR)
    samples_dir: Path = Field(default_factory=lambda: DEFAULT_SAMPLES_DATA_DIR)
    runs_dir: Path = Field(default_factory=lambda: DEFAULT_RUNS_DATA_DIR)
    tls_dir: Path = Field(default_factory=lambda: DEFAULT_TLS_DATA_DIR)
    audit_log_path: Path = Field(default_factory=lambda: DEFAULT_AUDIT_LOG_PATH)
    feedback_dataset_path: Path = Field(default_factory=lambda: DEFAULT_FEEDBACK_DATASET_PATH)

    @model_validator(mode="after")
    def _rebase_child_paths_if_custom_dir(self) -> DataConfig:
        if self.dir != DEFAULT_DATA_DIR:
            for field, default_val, rel_path in _DEFAULT_CHILD_DATA_PATHS:
                if getattr(self, field) == default_val:
                    setattr(self, field, self.dir / rel_path)
        return self


class TavilyConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)

    api_key: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DEVOPS_CLI_",
        extra="ignore",
        frozen=False,
        hide_input_in_errors=True,
    )
    github: GitHubConfig = GitHubConfig()
    ssh: SSHConfig = SSHConfig()
    repos: ReposConfig = ReposConfig()
    workspace: WorkspaceConfig = WorkspaceConfig()
    grafana: GrafanaConfig = GrafanaConfig()
    prometheus: PrometheusConfig = PrometheusConfig()
    argocd: ArgoCDConfig = ArgoCDConfig()
    qdrant: QdrantConfig = QdrantConfig()
    valkey: ValkeyConfig = ValkeyConfig()
    runs: RunsConfig = RunsConfig()
    tempo: TempoConfig = TempoConfig()
    pyroscope: PyroscopeConfig = PyroscopeConfig()
    telemetry: TelemetryConfig = TelemetryConfig()
    k8s: KubernetesConfig = KubernetesConfig()
    cloudflare: CloudflareConfig = CloudflareConfig()
    domain: str | None = Field(
        default=None,
        description="Default domain name for the environment or workstation",
    )
    sandbox: SandboxConfig = SandboxConfig()
    ci: CIConfig = CIConfig()
    ai: AIConfig = AIConfig()
    open_webui: OpenWebUIConfig = OpenWebUIConfig()
    data: DataConfig = DataConfig()
    service: ServiceConfig = ServiceConfig()
    tavily: TavilyConfig = TavilyConfig()
    # The values that `load_settings` returned, so `save_settings` writes only the keys that
    # changed after the load (#1999). Settings made in code have none, and start from the defaults.
    _loaded: dict[str, Any] | None = PrivateAttr(default=None)


_EPHEMERAL_CI_SECRETS: dict[str, str] = {}


def _keyring_get(key: str) -> str | None:
    import keyring
    from keyring.errors import KeyringLocked, NoKeyringError

    if key in _EPHEMERAL_CI_SECRETS:
        return _EPHEMERAL_CI_SECRETS[key]

    if not _ensure_keyring_backend():
        return None

    try:
        return keyring.get_password(KEYRING_SERVICE, key)
    except NoKeyringError:
        return None
    except KeyringLocked:
        logger.warning("Cannot read a secret: %s", _KEYRING_LOCKED_HINT)
        return None
    except Exception as exc:
        logger.warning("Failed to retrieve secret from OS Keyring: %s", type(exc).__name__)
        return None


def _keyring_has(key: str) -> bool:
    """Check whether a secret key exists in OS keyring or ephemeral store."""
    import keyring
    from keyring.errors import KeyringLocked, NoKeyringError

    if key in _EPHEMERAL_CI_SECRETS:
        return True

    if not _ensure_keyring_backend():
        return False

    try:
        val = keyring.get_password(KEYRING_SERVICE, key)
        return bool(val is not None)
    except KeyringLocked:
        logger.warning("Cannot check for a secret: %s", _KEYRING_LOCKED_HINT)
        return False
    except (NoKeyringError, Exception) as exc:
        logger.debug("Keyring check failed: %s", type(exc).__name__)
        return False


def _keyring_set(key: str, value: str) -> None:
    import keyring
    from keyring.errors import KeyringLocked, NoKeyringError

    if _headless_auth_enabled():
        _EPHEMERAL_CI_SECRETS[key] = value
        return

    if not _ensure_keyring_backend():
        _EPHEMERAL_CI_SECRETS[key] = value
        return

    try:
        keyring.set_password(KEYRING_SERVICE, key, value)
    except NoKeyringError:
        _EPHEMERAL_CI_SECRETS[key] = value
    except KeyringLocked as exc:
        raise KeyringLockedError(f"Cannot store {key}: {_KEYRING_LOCKED_HINT}") from exc
    except Exception as exc:
        raise SecretStorageError(f"Failed to store secret in keyring: {exc}") from exc


def _headless_auth_enabled() -> bool:
    """Report whether `DEVOPS_CLI_HEADLESS_AUTH` keeps secrets in the in-memory store."""
    import os

    return os.environ.get("DEVOPS_CLI_HEADLESS_AUTH", "").lower() in ("true", "1", "yes")


def require_persistent_keyring() -> None:
    """Raise unless an encrypted OS keyring is in use and unlocked.

    For commands that must never take a locked keyring for a missing entry, nor keep a value
    only in memory: a locked keyring raises `KeyringLockedError`; no encrypted backend, or the
    headless in-memory store, raises `KeyringUnavailableError`. The lock is probed by looking
    up an entry that is never stored, so no secret is read.
    """
    import keyring

    if _headless_auth_enabled():
        raise KeyringUnavailableError(
            "DEVOPS_CLI_HEADLESS_AUTH keeps secrets in memory only, so a value stored now would "
            "be lost when the command exits; unset it to use the OS keyring"
        )
    if not _ensure_keyring_backend():
        backend = type(keyring.get_keyring())
        backend_name = f"{backend.__module__}.{backend.__qualname__}"
        raise KeyringUnavailableError(
            f"no encrypted OS keyring backend is available (found {backend_name}); install and "
            "start one, such as gnome-keyring"
        )
    keyring_read(CONST_KEYRING_UNLOCK_PROBE_KEY)


def keyring_read(key: str) -> str | None:
    """Read a keyring entry, raising `KeyringLockedError` instead of returning None when locked."""
    import keyring
    from keyring.errors import KeyringError, KeyringLocked

    try:
        return keyring.get_keyring().get_password(KEYRING_SERVICE, key)
    except KeyringLocked as exc:
        raise KeyringLockedError(f"Cannot read {key}: {_KEYRING_LOCKED_HINT}") from exc
    except KeyringError as exc:
        raise SecretStorageError(f"Cannot read {key}: {type(exc).__name__}") from exc


def keyring_write(key: str, value: str) -> None:
    """Store a keyring entry in the OS keyring itself, never in the in-memory store."""
    import keyring
    from keyring.errors import KeyringError, KeyringLocked

    try:
        keyring.get_keyring().set_password(KEYRING_SERVICE, key, value)
    except KeyringLocked as exc:
        raise KeyringLockedError(f"Cannot store {key}: {_KEYRING_LOCKED_HINT}") from exc
    except KeyringError as exc:
        raise SecretStorageError(f"Cannot store {key}: {type(exc).__name__}") from exc


def keyring_delete(key: str) -> bool:
    """Delete a keyring entry from the OS keyring itself, returning False when there was none."""
    import keyring
    from keyring.errors import KeyringError, KeyringLocked, PasswordDeleteError

    try:
        keyring.get_keyring().delete_password(KEYRING_SERVICE, key)
    except PasswordDeleteError:
        return False
    except KeyringLocked as exc:
        raise KeyringLockedError(f"Cannot delete {key}: {_KEYRING_LOCKED_HINT}") from exc
    except KeyringError as exc:
        raise SecretStorageError(f"Cannot delete {key}: {type(exc).__name__}") from exc
    return True


def get_keyring_secret(key: str) -> str | None:
    """Public helper to retrieve a secret from OS Keyring or ephemeral store."""
    return _keyring_get(key)


def set_keyring_secret(key: str, value: str) -> bool:
    """Public helper to store a secret in OS Keyring or ephemeral store."""
    try:
        _keyring_set(key, value)
        return True
    except Exception as exc:
        logger.warning("Failed to set secret in OS Keyring: %s", type(exc).__name__)
        return False


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Merge override into base in-place; override wins on conflict, None skipped."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        elif value is not None:
            base[key] = value


def _apply_env_overrides(
    settings: Settings, option_keys: Iterable[str] = OPTION_TO_ENV_VAR
) -> None:
    """Allow devcontainer and shell environment variables to override file config."""
    env_data_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    if env_data_dir:
        settings.data.dir = Path(env_data_dir)

    for option_key in option_keys:
        if option_key in _SECRET_FIELDS:
            continue
        env_var = OPTION_TO_ENV_VAR[option_key]
        env_value = os.environ.get(env_var)
        if env_value in (None, ""):
            continue
        try:
            dotted_set(settings, option_key, env_value)
        except (AttributeError, ValueError) as exc:
            # An override that cannot apply is an error, not a silent no-op.
            raise ConfigurationError(
                f"Environment variable {env_var} cannot set {option_key}: {exc}", key=option_key
            ) from exc


def _resolve_data_config(raw_data: dict[str, Any], current_data_dir: Path) -> DataConfig:
    """Resolve DataConfig with environment variable and explicit YAML overrides."""
    env_data_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    explicit_data: dict[str, Any] = {"dir": current_data_dir}

    for field_name, env_v in _CHILD_DATA_ENV_MAP.items():
        env_val = os.environ.get(env_v)
        if env_val:
            explicit_data[field_name] = Path(env_val)
        elif field_name in raw_data and not env_data_dir:
            raw_path = Path(raw_data[field_name])
            if (
                current_data_dir == DEFAULT_DATA_DIR
                or raw_path != _DEFAULT_CHILD_DATA_MAP[field_name]
            ):
                explicit_data[field_name] = raw_path

    return DataConfig.model_validate(explicit_data)


_FileStamp = tuple[str, int, int]
_ConfigCacheEntry = tuple[Path | None, tuple[_FileStamp, _FileStamp], dict[str, Any]]

_CONFIG_CACHE_LOCK = threading.Lock()
# Keyed on everything that selects which files are read -- the global path (tests rebind
# it), DEVOPS_CLI_CONFIG, the working directory the project lookup walks up from, and whether the
# rule for a command that reads a tree it does not own holds, which skips that lookup (#972). The
# rule's check of the working directory's repository is cached in `core.repo`, so the key costs no
# walk of the tree.
_CONFIG_CACHE: dict[tuple[str, str, str, bool], _ConfigCacheEntry] = {}


def _file_stamp(path: Path | None) -> _FileStamp:
    """Summarise a configuration file as its path, modification time and size.

    A file that is absent stamps as zeroes rather than being omitted, so that creating it
    later reads as a change instead of as the same "no file" it was before.
    """
    if path is None:
        return ("", 0, 0)
    try:
        stat = path.stat()
    except OSError:
        return (str(path), 0, 0)
    return (str(path), stat.st_mtime_ns, stat.st_size)


def _stamps_are_settled(stamps: tuple[_FileStamp, _FileStamp]) -> bool:
    """Report whether every stamped file has been still long enough to be trusted."""
    cutoff_ns = (time.time() - CONST_SETTINGS_CACHE_SETTLE_SECONDS) * 1_000_000_000
    return all(mtime_ns < cutoff_ns for _, mtime_ns, _ in stamps)


def _read_config_layers(project_path: Path | None) -> dict[str, Any]:
    """Merge the global configuration file with the project layer, the project winning."""
    raw: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    if project_path and project_path.exists():
        project_raw: dict[str, Any] = yaml.safe_load(project_path.read_text(encoding="utf-8")) or {}
        _deep_merge(raw, project_raw)
    return raw


def _merged_config_data() -> dict[str, Any]:
    """Return the merged file configuration, re-reading only when a source file changed.

    Settings are consulted from per-request paths, yet each call otherwise walked the
    directory tree hunting for a project config and re-parsed both YAML layers to arrive
    at the identical mapping. Reuse is conditional on the files that supplied the values
    still carrying the stamp they had when parsed, so an edit made by any process is
    honoured on the next call rather than a snapshot living for the process lifetime.
    Only the discovery walk is taken on trust: a project config file created after the
    first load is picked up once the cache is reset, because a stamp of a file that did
    not exist cannot report where a new one appeared.

    The caller receives a copy, since the settings built from this mapping are mutable and
    a caller editing one before saving must not rewrite what every later load sees.
    """
    cache_key = (
        str(CONFIG_PATH),
        os.environ.get(PROJECT_CONFIG_ENV, ""),
        os.getcwd(),
        reads_untrusted_trees(),
    )
    with _CONFIG_CACHE_LOCK:
        entry = _CONFIG_CACHE.get(cache_key)
    if entry is not None:
        cached_path, cached_stamps, cached_data = entry
        if cached_stamps == (_file_stamp(CONFIG_PATH), _file_stamp(cached_path)):
            return copy.deepcopy(cached_data)

    # Stamped before the read, so a write that races the read leaves a stamp that looks
    # older than the content held -- which costs a re-read, never a stale answer.
    project_path = _find_project_config_path()
    stamps = (_file_stamp(CONFIG_PATH), _file_stamp(project_path))
    data = _read_config_layers(project_path)
    if _stamps_are_settled(stamps):
        with _CONFIG_CACHE_LOCK:
            # A different key means a different working directory or configuration path,
            # which strands the previous entry; keeping it would grow without bound.
            _CONFIG_CACHE.clear()
            _CONFIG_CACHE[cache_key] = (project_path, stamps, copy.deepcopy(data))
    return data


def reset_settings_cache() -> None:
    """Discard parsed configuration so the next load reads the files from disk again."""
    with _CONFIG_CACHE_LOCK:
        _CONFIG_CACHE.clear()


def clear_ephemeral_ci_secrets() -> None:
    """Clear the in-process ephemeral CI secrets store."""
    _EPHEMERAL_CI_SECRETS.clear()


def load_settings() -> Settings:
    """Load settings: global config → project config → env vars (each layer wins).

    While a command that reads a tree it does not own runs, such as a review, from a repository
    other than devops-cli's own, the project layer is only the file `DEVOPS_CLI_CONFIG` names
    (`_find_project_config_path`, #972).
    """
    raw = _merged_config_data()

    try:
        settings = Settings.model_validate(raw)
    except ValidationError as exc:
        # A key that a section refuses gets its file, its line and the command that removes it,
        # which the error of pydantic does not give (#2201).
        from devops_cli.config import unknown_keys

        refused = unknown_keys.refused_keys(exc)
        if not refused:
            raise
        project_path = _find_project_config_path()
        raise unknown_keys.unknown_keys_error(
            refused, (project_path, CONFIG_PATH), active=project_path or CONFIG_PATH
        ) from exc
    # Environment overrides stay outside the cache: they cost microseconds to reapply, and
    # a variable exported after the first load must still take effect.
    _apply_env_overrides(settings)

    raw_data = raw.get("data", {}) if isinstance(raw.get("data"), dict) else {}
    settings.data = _resolve_data_config(raw_data, settings.data.dir)
    settings._loaded = settings.model_dump(mode="json")

    return settings


def telemetry_from_environment() -> TelemetryConfig:
    """The telemetry section from its registered variables alone, for settings that cannot load.

    An unreadable configuration layer, or a registered variable that cannot apply, may be the one
    turning export off, so export stays off unless `DEVOPS_CLI_TELEMETRY_ENABLED` turns it on: an
    opt-out never fails open to the default (#956).
    """
    try:
        fallback = Settings.model_validate({"telemetry": {"enabled": False}})
        _apply_env_overrides(fallback, _TELEMETRY_ENV_OPTIONS)
        return fallback.telemetry
    except ConfigurationError, ValidationError:
        return TelemetryConfig(enabled=False)


def _match_dir_candidate(d: Path, candidate_names: tuple[str, ...]) -> Path | None:
    """Find the first non-forbidden regular config file candidate in directory d."""
    from devops_cli.core.paths import is_forbidden_system_path

    for name in candidate_names:
        p = d / name
        if p.is_file() and not p.is_symlink():
            resolved = p.resolve()
            if not is_forbidden_system_path(resolved):
                return resolved
    return None


def _find_project_config_path(base_dir: Path | None = None) -> Path | None:
    """Locate candidate project/devcontainer config file from env, base_dir, or ancestor directories.

    While a command that reads a tree it does not own runs, such as a review, only the file
    `DEVOPS_CLI_CONFIG` names counts (#972). The walk would find a config the tree under review
    commits, which could name the gateway its model traffic and API key go to; a project config
    is a feature for the user's own repositories, and naming one is the explicit opt-in. The walk
    still runs in devops-cli's own repository, whose code already runs in this process
    (`reads_untrusted_trees`, `core.repo.is_own_source_repository`).
    """
    env_config = os.environ.get(PROJECT_CONFIG_ENV)
    if env_config:
        env_p = Path(env_config).resolve()
        if not env_p.is_dir():
            return env_p
    if reads_untrusted_trees():
        return None

    start_dir = (base_dir or Path.cwd()).resolve()
    for d in (start_dir, *start_dir.parents):
        candidate = _match_dir_candidate(d, PROJECT_CONFIG_CANDIDATES)
        if candidate is not None:
            return candidate
        if (d / ".git").exists() or (d / ".devcontainer").exists():
            break
    return None


def get_active_config_path(base_dir: Path | None = None) -> Path:
    """Return active config file path (DEVOPS_CLI_CONFIG > project config > ~/.config)."""
    env_config = os.environ.get(PROJECT_CONFIG_ENV)
    if env_config:
        from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal
        from devops_cli.exceptions.security import SecurityError

        validate_no_path_traversal(env_config, label="DEVOPS_CLI_CONFIG")
        resolved = Path(env_config).resolve()
        if is_forbidden_system_path(resolved):
            raise SecurityError(
                f"DEVOPS_CLI_CONFIG cannot target forbidden system path: '{env_config}'."
            )
        return resolved
    found = _find_project_config_path(base_dir=base_dir)
    return found if found is not None else CONFIG_PATH


def save_settings(
    settings: Settings, target_path: Path | None = None, *, keys: Iterable[str] = ()
) -> None:
    """Write the settings that changed after `load_settings` returned them into a config file.

    Secrets stay in the keyring only. The write edits the file in place (`round_trip`, #1999): it
    writes only the keys whose values changed, and it keeps the comments, the order of the keys and
    the keys that the model does not know. A value that a default, another config file or an
    environment variable gives, and that did not change, stays out of the file. Settings made in
    code, not by `load_settings`, count each value that differs from the default as a change.
    `keys` names dotted keys to write also when they hold the value that they had after the load,
    such as the key that a person names to `devops config set`.

    A write that changes the file first copies the file beside itself, and then records the
    command and the changed keys in the audit log (`write_history`, #1921). A write that leaves
    every byte of the file as it is writes nothing.
    """
    from devops_cli.config import round_trip

    baseline = settings._loaded
    if baseline is None:
        baseline = Settings.model_validate({}).model_dump(mode="json")
    current = settings.model_dump(mode="json")
    changed = round_trip.changes(baseline, current)
    values = round_trip.leaves(current)
    for key in keys:
        path = tuple(_canonical_key(key).split("."))
        if path in values:
            changed.setdefault(path, values[path])
    if changed:
        _write_changes(target_path or get_active_config_path(), changed)
    # The writer knows the values changed, so it says so outright rather than leaving the
    # next load to infer it from a timestamp the filesystem may not yet have advanced.
    reset_settings_cache()


def _write_changes(dest_path: Path, changed: dict[tuple[str, ...], Any]) -> None:
    """Write the changed keys into `dest_path`, with its copy and its audit record."""
    from devops_cli.config import round_trip

    previous = dest_path.read_bytes() if dest_path.is_file() else None
    text = previous.decode("utf-8") if previous is not None else ""
    content = round_trip.edit(text, changed, name=str(dest_path)).encode("utf-8")
    _write_content(dest_path, previous, content)


def _write_content(dest_path: Path, previous: bytes | None, content: bytes) -> Path | None:
    """Write `content` into `dest_path` when it differs from the `previous` content: copy the file
    first, and then record the write in the audit log. Return the copy, or None when the write
    changes nothing or the file did not exist."""
    from devops_cli.config import write_history

    if content == previous:
        return None
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    backup = write_history.back_up(dest_path)
    tmp = dest_path.with_suffix(".yaml.tmp")
    tmp.write_bytes(content)
    os.replace(tmp, dest_path)
    write_history.record_write(dest_path, previous, content, backup)
    return backup


def remove_config_key(
    key: str, target_path: Path | None = None, *, dry_run: bool = False
) -> ConfigKeyRemoval:
    """Remove the dotted `key` and its value from the active config file, or from `target_path`.

    The removal edits the text of the file (`round_trip`) and loads no settings, so it also removes
    a key that stops the settings from loading (#2201). It keeps every other line and comment. A
    write first copies the file beside itself, and then records the removed key in the audit log,
    as a save does. A dry run returns the same removal, with no copy, and writes nothing. A key that
    the file does not hold raises ConfigurationError, and the file stays as it is.
    """
    import difflib

    from devops_cli.config import round_trip
    from devops_cli.models.config import ConfigKeyRemoval

    dest_path = target_path or get_active_config_path()
    previous = dest_path.read_bytes() if dest_path.is_file() else None
    text = previous.decode("utf-8") if previous is not None else ""
    found = round_trip.find(text, _canonical_key(key), name=str(dest_path))
    if found is None:
        raise ConfigurationError(
            ERRORS.config.key_not_in_file.format(path=dest_path, key=key), key=key
        )
    path, line = found
    content = round_trip.edit(text, {path: round_trip.ABSENT}, name=str(dest_path))
    diff = difflib.unified_diff(
        text.splitlines(),
        content.splitlines(),
        fromfile=str(dest_path),
        tofile=str(dest_path),
        n=0,
        lineterm="",
    )
    backup = None
    if not dry_run:
        backup = _write_content(dest_path, previous, content.encode("utf-8"))
        reset_settings_cache()
    return ConfigKeyRemoval(
        path=str(dest_path),
        key=".".join(path),
        line=line,
        diff="".join(f"{diff_line}\n" for diff_line in diff),
        backup=str(backup) if backup is not None else None,
    )


# NOTE (Design Justification - SECURITY.md, principle 1): Every credential resolves through the single
# provider chain in `devops_cli.security.secrets`, which walks OS keyring -> Vault ->
# environment -> configuration in that fixed order and records an audit entry naming the
# provider that answered (never the value). Environment variables remain an intentional
# fallback for non-interactive CI runners. Previously each getter below carried its own
# hand-written ladder, so two secrets could disagree about precedence and no lookup was
# observable.
def _resolve(option: str, settings: Settings) -> str | None:
    """Resolve one managed credential through the unified provider chain."""
    from devops_cli.security.secrets import build_secret_registry, get_resolver

    ref = build_secret_registry(_KEYRING_KEYS).get(option)
    if ref is None:
        return _keyring_get(_KEYRING_KEYS[option])
    # Bind the caller's settings so configuration-sourced values reflect this call, not a
    # snapshot captured when the process-wide resolver was first constructed.
    return get_resolver().resolve(ref, settings_source=lambda: settings)


def get_grafana_token(settings: Settings) -> str | None:
    """Resolve the Grafana API token, rejecting masked placeholder values."""
    token = _resolve(opt.GRAFANA_TOKEN, settings)
    return token if token and not token.startswith("*") else None


def get_grafana_password(settings: Settings) -> str | None:
    """Resolve the Grafana account password."""
    return _resolve(opt.GRAFANA_PASSWORD, settings)


def get_argocd_token(settings: Settings) -> str | None:
    """Resolve the ArgoCD API token, rejecting masked placeholder values."""
    token = _resolve(opt.ARGOCD_TOKEN, settings)
    # A masked value indicates a redacted export was re-imported, not a usable token.
    return token if token and not token.startswith("*") else None


def get_argocd_password(settings: Settings) -> str | None:
    """Resolve the ArgoCD account password."""
    return _resolve(opt.ARGOCD_PASSWORD, settings)


def get_ai_api_key(settings: Settings) -> str | None:
    """Resolve the AI provider API key."""
    return _resolve(opt.AI_API_KEY, settings)


def get_qdrant_api_key(settings: Settings) -> str | None:
    """Resolve the Qdrant API key."""
    return _resolve(opt.QDRANT_API_KEY, settings)


def get_valkey_password(settings: Settings) -> str | None:
    """Resolve the Valkey password."""
    return _resolve(opt.VALKEY_PASSWORD, settings)


def get_runs_index_password(settings: Settings) -> str | None:
    """Resolve the password of the Valkey holding the shared run index."""
    return _resolve(opt.RUNS_INDEX_PASSWORD, settings)


def get_gitea_admin_password(settings: Settings) -> str | None:
    """Resolve the password of Gitea's admin user."""
    return _resolve(opt.GITEA_ADMIN_PASSWORD, settings)


def get_logfire_token(settings: Settings) -> str | None:
    """Resolve the Logfire telemetry write token."""
    return _resolve(opt.TELEMETRY_LOGFIRE_TOKEN, settings)


def get_cloudflare_api_token(settings: Settings) -> str | None:
    """Resolve the Cloudflare API token."""
    return _resolve(opt.CLOUDFLARE_API_TOKEN, settings)


def get_service_webhook_secrets(settings: Settings) -> str | None:
    """Resolve the JSON mapping of repo to webhook secret."""
    return _resolve(opt.SERVICE_WEBHOOK_SECRETS, settings)


def get_tavily_api_key(settings: Settings | None = None) -> str | None:
    """Resolve the Tavily search API key."""
    active_settings = settings or load_settings()
    return _resolve(opt.TAVILY_API_KEY, active_settings)


def _canonical_key(key: str) -> str:
    """The settings key that a dotted key names: `otel.<field>` names `telemetry.<field>`."""
    return "telemetry." + key[5:] if key.startswith("otel.") else key


def dotted_get(settings: Settings, key: str) -> Any:
    """Get a config value by dotted key, e.g. 'github.default_org'."""
    return operator.attrgetter(_canonical_key(key))(settings)


def _coerce_setting_value(new_value: Any, is_list_field: bool) -> Any:
    """Split comma-separated strings for list fields, leaving other values for Pydantic validation."""
    if is_list_field:
        if isinstance(new_value, str):
            trimmed = new_value.strip()
            if trimmed.startswith("[") and trimmed.endswith("]"):
                try:
                    parsed = json.loads(trimmed)
                    if isinstance(parsed, list):
                        return [str(item) for item in parsed if item]
                except json.JSONDecodeError:
                    pass
            return [v.strip() for v in trimmed.split(",") if v.strip()]
        return new_value
    return new_value


def dotted_set(settings: Settings, key: str, value: Any) -> None:
    """Set a config value by dotted key, at any depth. Secret keys go to the OS keyring.

    `ai.tasks.chat.model` walks the nested sections; a key naming no field raises
    ConfigurationError rather than setting nothing.
    """
    if key in _SECRET_FIELDS:
        _keyring_set(_KEYRING_KEYS[key], value)
        return
    *path, field_name = _canonical_key(key).split(".")
    if not path:
        target = getattr(settings, field_name, None)
        if isinstance(target, BaseModel):
            raise ConfigurationError(
                f"Cannot set top-level section '{field_name}' directly to a string. "
                f"Use dotted key (e.g. '{field_name}.<field>').",
                key=field_name,
            )
        field_info = type(settings).model_fields.get(field_name)
        if field_info is None:
            raise ConfigurationError(f"Unknown configuration key '{key}'.", key=key)
        is_list = _is_list_annotation(field_info.annotation)
        coerced = _coerce_setting_value(value, is_list)
        try:
            setattr(settings, field_name, coerced)
        except ValidationError as exc:
            raise ValueError(_format_validation_error(exc)) from exc
        return
    section = _settings_section(settings, path, key)
    field_info = type(section).model_fields.get(field_name)
    if field_info is None:
        raise ConfigurationError(f"Unknown configuration key '{key}'.", key=key)
    is_list = _is_list_annotation(field_info.annotation)
    coerced = _coerce_setting_value(value, is_list)
    try:
        setattr(section, field_name, coerced)
    except ValidationError as exc:
        raise ValueError(_format_validation_error(exc, tuple(path))) from exc


def _settings_section(settings: Settings, path: list[str], key: str) -> BaseModel:
    """The nested settings model a dotted key's field belongs to."""
    section: BaseModel = settings
    for part in path:
        child = getattr(section, part, None)
        if not isinstance(child, BaseModel):
            raise ConfigurationError(f"Unknown configuration key '{key}'.", key=key)
        section = child
    return section
