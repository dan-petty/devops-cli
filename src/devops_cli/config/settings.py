"""Configuration settings resolution and Pydantic models."""

from __future__ import annotations

import copy
import json
import logging
import operator
import os
import stat
import threading
import time
import types
import typing
from collections.abc import Collection, Iterable, Iterator
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
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_SETTINGS_CACHE_SETTLE_SECONDS,
)
from devops_cli.config.constants import (
    CONST_CONFIG_PATH as CONFIG_PATH,
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
    DEFAULT_AI_IMPLEMENT_CONTEXT_WINDOW,
    DEFAULT_AI_IMPLEMENT_MODEL,
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
    DEFAULT_ROADMAP_ALTERNATIVES_LIMIT,
    DEFAULT_ROADMAP_ALTERNATIVES_RECHECK_DAYS,
    DEFAULT_ROADMAP_ALTERNATIVES_RETRY_DAYS,
    DEFAULT_ROADMAP_IMPLEMENT_REPAIR_ROUNDS,
    DEFAULT_ROADMAP_STAGE_FILTER,
    DEFAULT_ROADMAP_STAGE_LIMIT,
    DEFAULT_ROADMAP_STAGE_STEP_TOKENS,
    DEFAULT_RUNS_DATA_DIR,
    DEFAULT_SAMPLES_DATA_DIR,
    DEFAULT_SANDBOX_EXCLUDE_HOME,
    DEFAULT_SERVICE_DRAIN_TIMEOUT_SECONDS,
    DEFAULT_SERVICE_GITHUB_REQUESTS_PER_HOUR,
    DEFAULT_SERVICE_MODEL_CALL_CONCURRENCY,
    DEFAULT_SERVICE_POLL_INTERVAL_SECONDS,
    DEFAULT_SSH_KEY_DIR,
    DEFAULT_SSH_KEY_PREFIX,
    DEFAULT_SSH_ROTATION_DAYS,
    DEFAULT_THREAT_INTEL_CACHE_TTL_SECONDS,
    DEFAULT_TLS_DATA_DIR,
    DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_VALKEY_TIMEOUT_SECONDS,
    DEFAULT_VALKEY_URL,
    DEFAULT_WORKSPACE_FILE,
)
from devops_cli.config.env import (
    ENV_OTEL_EXPORTER_OTLP_ENDPOINT,
    Variable,
    keyring_names,
    secret_keys,
    setting_variables,
)
from devops_cli.config.os_keyring import store_keyring_secret
from devops_cli.core.dns_names import OptionalConfiguredDomain
from devops_cli.core.untrusted_trees import reads_untrusted_trees
from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import ERRORS
from devops_cli.roadmap.stage_filter import split_filter_entry
from devops_cli.valkey.endpoint import ValkeyEndpoint, parse_valkey_url

if typing.TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from devops_cli.models.config import ConfigKeyRemoval

logger = logging.getLogger(__name__)

_SECRET_FIELDS: frozenset[str] = secret_keys()
_KEYRING_KEYS: dict[str, str] = keyring_names()
# The options that still decide telemetry when the rest of the settings cannot load (#956).
_TELEMETRY_ENV_OPTIONS: tuple[str, ...] = ("telemetry.enabled", "telemetry.endpoint")


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
    default_org: Annotated[str | None, Variable()] = Field(
        default=None, description="Default GitHub organization"
    )


class SSHConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    key_dir: Annotated[Path, Variable()] = Field(
        default=DEFAULT_SSH_KEY_DIR, description="Directory for SSH key pairs"
    )
    key_prefix: Annotated[str | None, Variable()] = Field(
        default=DEFAULT_SSH_KEY_PREFIX,
        description="Prefix for generated SSH keys (defaults to devcontainer name or basename pwd)",
    )
    rotation_days: Annotated[int, Variable()] = Field(
        description="SSH key rotation interval in days", default=DEFAULT_SSH_ROTATION_DAYS, gt=0
    )


class ReposConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    base_dir: Annotated[Path, Variable()] = Field(
        default=DEFAULT_REPOS_BASE_DIR, description="Base directory for cloned repositories"
    )


class WorkspaceConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    file: Annotated[Path, Variable()] = Field(
        default=DEFAULT_WORKSPACE_FILE, description="Path to VS Code workspace file"
    )


class GrafanaConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: Annotated[ServiceUrlStr | None, Variable()] = Field(
        default=None, description="Grafana service URL"
    )


class PrometheusConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: Annotated[ServiceUrlStr | None, Variable()] = Field(
        default=None, description="Prometheus service URL"
    )


class ArgoCDConfig(BaseModel):
    """Argo CD's server, and the GitHub App that its GitHub notifier acts as (#2000).

    The App's private key is the managed credential `argocd.github_app_private_key`. The push
    writes the two IDs and the key to Secret `argocd/argocd-notifications-secret`.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: Annotated[ServiceUrlStr | None, Variable()] = Field(
        default=None, description="ArgoCD service URL"
    )
    github_app_id: Annotated[int | None, Variable()] = Field(
        default=None,
        gt=0,
        description="ID of the GitHub App that Argo CD's GitHub notifier acts as",
    )
    github_app_installation_id: Annotated[int | None, Variable()] = Field(
        default=None,
        gt=0,
        description="ID of the installation of Argo CD's notifier App on the managed repositories",
    )


class QdrantConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: Annotated[ServiceUrlStr | None, Variable()] = Field(
        default=None, description="Qdrant vector database server URL"
    )
    collection_prefix: Annotated[str, Variable()] = Field(
        default="devops", description="Prefix for Qdrant collection names"
    )
    api_key: str | None = None
    timeout: Annotated[float, Variable()] = Field(
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
    index_url: Annotated[str | None, Variable()] = Field(
        default=None,
        description="Valkey holding the run index shared by workstations (set by `devops ai runs connect`)",
    )


class ValkeyConfig(BaseModel):
    """The Valkey that the caches, the dashboard and `devops valkey` use.

    `url` is checked when a client reads `endpoint`, not when the settings load, so a URL that is
    not valid stops only the Valkey commands. A file that still holds the removed `host`, `port`
    and `db` keys loads, and the next save drops them.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: Annotated[str | None, Variable()] = Field(
        default=DEFAULT_VALKEY_URL,
        description=(
            "The Valkey endpoint, such as `valkeys://example.com:6380/0`: the scheme, the host, the "
            "port and the database. The scheme `valkeys` connects over TLS and checks the "
            "certificate against the host. The scheme `valkey` connects in plaintext. The URL holds "
            "no password: `valkey.password` is in the OS keyring"
        ),
    )
    password: str | None = None
    timeout: Annotated[float, Variable()] = Field(
        description=f"Valkey network socket connection/read timeout in seconds; the shared cache of embeddings, threat intel and library symbols waits at most {DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS} s for a connection (default: {DEFAULT_VALKEY_TIMEOUT_SECONDS})",
        default=DEFAULT_VALKEY_TIMEOUT_SECONDS,
        gt=0,
        allow_inf_nan=False,
    )
    threat_intel_ttl: int = Field(default=DEFAULT_THREAT_INTEL_CACHE_TTL_SECONDS, gt=0)

    @property
    def endpoint(self) -> ValkeyEndpoint:
        """The endpoint of `url`, or of the default URL when `url` is unset or empty.

        A URL that is not valid raises `ConfigurationError` naming `valkey.url`.
        """
        return parse_valkey_url(
            self.url or DEFAULT_VALKEY_URL,
            setting="valkey.url",
            written_by="`devops k8s configure-urls` or `devops config set valkey.url`",
        )


class TempoConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: ServiceUrlStr | None = None


class PyroscopeConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    url: ServiceUrlStr | None = None


class TelemetryConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    enabled: Annotated[bool, Variable()] = Field(
        default=True, description="Export OpenTelemetry traces and metrics"
    )
    # Unset rather than the built-in endpoint, so OpenTelemetry's own variable can name the
    # collector when devops-cli's configuration does not.
    endpoint: Annotated[HttpUrlStr | None, Variable()] = Field(
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
    capture_llm_content: Annotated[bool, Variable()] = Field(
        default=False,
        description="Record LLM prompt and reply text in OpenTelemetry and Logfire telemetry spans. "
        "Off by default to prevent exposure of sensitive data",
    )
    logfire: bool = False
    logfire_token: str | None = None
    logfire_send_to_logfire: bool | str = "if-token-present"


class CIConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    gate_slots: Annotated[int | None, Variable()] = Field(
        default=None,
        gt=0,
        description=(
            "Number of CPU-heavy devops ci gates that run at once on this host "
            "(default: one for each 16 CPUs)"
        ),
    )


class SandboxConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    exclude_home_dir: Annotated[bool, Variable()] = Field(
        default=DEFAULT_SANDBOX_EXCLUDE_HOME,
        description="Exclude user home directory entirely from sandbox access (/home/**/* and ~/**/*)",
    )


class KubernetesConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    context: Annotated[str, Variable()] = Field(
        default="minikube",
        description="Active Kubernetes cluster context name (e.g. minikube, docker-desktop, kind-cluster, or cloud context)",
    )
    domain: Annotated[OptionalConfiguredDomain, Variable()] = Field(
        default=None,
        description="Base domain name for homelab ingress routes and tunnel services (e.g. example.com)",
    )
    tunnel_host: Annotated[OptionalConfiguredDomain, Variable()] = Field(
        default=None,
        description="Hostname of the Kubernetes API route through the Cloudflare tunnel, which 'devops k8s tunnel start' forwards to a local port (e.g. k8s.example.com)",
    )
    addressing: str | None = Field(
        default=None,
        description="Default addressing mode for cluster services: nodeport, proxy, or fqdn.",
    )


class CloudflareAccessConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    allowed_emails: Annotated[list[str], Variable()] = Field(
        default_factory=list,
        description="List of email addresses permitted to authenticate through Cloudflare Access",
    )
    bypass_ips: Annotated[list[str], Variable()] = Field(
        default_factory=list,
        description="List of public IP addresses or CIDR blocks permitted to bypass Cloudflare Access authentication",
    )
    public_ip_bypass: Annotated[str | None, Variable()] = Field(
        default=None,
        description="Homelab public IP address or CIDR block permitted to bypass Cloudflare Access authentication",
    )


class CloudflareConfig(BaseModel):
    model_config = ConfigDict(frozen=False, validate_assignment=True, hide_input_in_errors=True)
    domain: Annotated[OptionalConfiguredDomain, Variable()] = Field(
        default=None,
        description="Root or zone domain name managed in Cloudflare (e.g. example.com)",
    )
    tunnel: Annotated[str | None, Variable()] = Field(
        default=None,
        description="Cloudflare tunnel name or identifier (e.g. homelab)",
    )
    account_id: Annotated[str | None, Variable()] = Field(
        default=None,
        description="Cloudflare Account ID",
    )
    zone_id: Annotated[str | None, Variable()] = Field(
        default=None,
        description="Cloudflare Zone ID",
    )
    public_ip_bypass: Annotated[str | None, Variable()] = Field(
        default=None,
        description="Homelab public IP address or CIDR block permitted to bypass Cloudflare Access authentication",
    )
    access: CloudflareAccessConfig = Field(
        default_factory=CloudflareAccessConfig,
        description="Cloudflare Zero Trust Access application and policy configuration",
    )


class AIRAGConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)
    enabled: Annotated[bool, Variable()] = Field(
        default=True,
        description="Retrieve related code and documents from the Qdrant index for AI tasks",
    )
    top_k: Annotated[int, Variable()] = Field(
        description="Number of results that a RAG retrieval returns",
        default=DEFAULT_RAG_TOP_K,
        gt=0,
    )
    score_threshold: Annotated[float, Variable()] = Field(
        description="Lowest score, from 0 to 1, of a result that a RAG retrieval keeps",
        default=DEFAULT_RAG_SCORE_THRESHOLD,
        ge=0.0,
        le=1.0,
        allow_inf_nan=False,
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
    provider: str | None = Field(
        default=None, description="AI provider of this task, in place of `ai.provider`"
    )
    model: str | None = Field(
        default=None, description="AI model of this task, in place of `ai.model`"
    )
    reasoning_effort: str | None = Field(
        default=None, description="Reasoning effort of this task, in place of `ai.reasoning_effort`"
    )
    supports_reasoning: bool | None = None
    use_model_sampling: bool | None = Field(
        default=None,
        description="Leave sampling parameters to the model. When true, requests carry neither temperature, top_p nor seed.",
    )
    temperature: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    context_window: int | None = Field(default=None, gt=0)
    num_ctx: int | None = Field(default=None, gt=0)
    max_tokens: int | None = Field(default=None, gt=0)
    ollama_urls: list[HttpUrlStr] | None = Field(
        default=None, description="Ollama service URLs of this task, in place of `ai.ollama_urls`"
    )
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


class AIEmbeddingTaskOverride(AITaskOverride):
    """The embedding task's override. Its model is the embedding model until a source sets another,
    so a variable or a config file that sets only another field of the task keeps it."""

    model: str | None = Field(
        default=DEFAULT_RAG_EMBEDDING_MODEL,
        description="AI model of this task, in place of `ai.model`",
    )


class AIImplementTaskOverride(AITaskOverride):
    """The implement task's override (#2664). Its model is the coder route and its window is the
    window of that route, until a source sets another, so a config file that sets only another
    field of the task keeps both."""

    model: str | None = Field(
        default=DEFAULT_AI_IMPLEMENT_MODEL,
        description="AI model of this task, in place of `ai.model`",
    )
    context_window: int | None = Field(
        default=DEFAULT_AI_IMPLEMENT_CONTEXT_WINDOW,
        gt=0,
        description="Context window of this task in tokens, in place of `ai.context_window`",
    )


# The fields of a task that a variable sets, such as `DEVOPS_CLI_AI_TASK_CHAT_MODEL`.
_TASK_VARIABLES: tuple[str, ...] = ("provider", "model", "reasoning_effort", "ollama_urls")


class AITasksConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=False, validate_assignment=True, hide_input_in_errors=True
    )
    chat: Annotated[AITaskOverride, Variable(fields=_TASK_VARIABLES)] = AITaskOverride()
    metadata: Annotated[AITaskOverride, Variable(fields=_TASK_VARIABLES)] = Field(
        default_factory=AITaskOverride,
        description="The task of `analyze --enhanced` and `ai agents`",
    )
    analysis: Annotated[AITaskOverride, Variable(fields=_TASK_VARIABLES)] = AITaskOverride()
    verification: AITaskOverride = AITaskOverride()
    compose: AITaskOverride = AITaskOverride()
    embedding: Annotated[
        AIEmbeddingTaskOverride, Variable(fields=(*_TASK_VARIABLES, "timeout"))
    ] = AIEmbeddingTaskOverride()
    implement: AIImplementTaskOverride = Field(
        default_factory=AIImplementTaskOverride,
        description="The task of `devops roadmap implement`: one step of a staged change",
    )
    triage: AITaskOverride = Field(
        default_factory=AITaskOverride,
        description="The task of roadmap intake",
    )


class AIConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=False, validate_assignment=True, hide_input_in_errors=True
    )
    provider: Annotated[str, Variable()] = Field(
        default=DEFAULT_AI_PROVIDER, description="AI provider (ollama | claude | copilot | openai)"
    )
    model: Annotated[str, Variable()] = Field(
        default=DEFAULT_AI_MODEL, description="Default AI model name"
    )
    api_key: str | None = Field(default=None, repr=False)
    reference_model: Annotated[str, Variable()] = Field(
        default=DEFAULT_AI_REFERENCE_MODEL,
        description="Hosted chat model whose genai-prices price values the local chat tokens in the AI spend reports",
    )
    reference_embedding_model: Annotated[str, Variable()] = Field(
        default=DEFAULT_AI_REFERENCE_EMBEDDING_MODEL,
        description="Hosted embedding model whose genai-prices price values the local embedding tokens in the AI spend reports",
    )
    reference_provider: Annotated[str, Variable()] = Field(
        default=DEFAULT_AI_REFERENCE_PROVIDER,
        description="Provider in genai-prices of the two reference models",
    )
    hardware_cost_usd: Annotated[float, Variable()] = Field(
        description="Cost in USD of the local AI hardware, which `devops ai cost` compares with the savings",
        default=DEFAULT_AI_HARDWARE_COST_USD,
        ge=0.0,
        allow_inf_nan=False,
    )
    reasoning_effort: Annotated[str | None, Variable()] = Field(
        default=DEFAULT_AI_REASONING_EFFORT,
        description="AI reasoning effort level (low | medium | high)",
    )
    supports_reasoning: bool = DEFAULT_AI_SUPPORTS_REASONING
    use_model_sampling: bool = Field(
        default=False,
        description="Leave sampling parameters to the model. When true, requests carry neither temperature, top_p nor seed.",
    )
    temperature: float = Field(default=DEFAULT_AI_TEMPERATURE, ge=0.0, allow_inf_nan=False)
    top_p: float = Field(default=DEFAULT_AI_TOP_P, ge=0.0, le=1.0, allow_inf_nan=False)
    context_window: int = Field(default=DEFAULT_AI_CONTEXT_WINDOW, gt=0)
    num_ctx: int | None = Field(default=None, gt=0)
    max_tokens: int | None = Field(default=None, gt=0)
    ollama_urls: Annotated[list[HttpUrlStr], Variable()] = Field(
        description="Ollama service URLs (comma-separated)", default_factory=list
    )
    ollama_max_parallel: Annotated[int, Variable()] = Field(
        description="Maximum parallel requests per Ollama host",
        default=DEFAULT_OLLAMA_MAX_PARALLEL,
        gt=0,
    )
    gateway_provider: str = DEFAULT_AI_GATEWAY_PROVIDER
    gateway_url: Annotated[HttpUrlStr | None, Variable()] = Field(
        default=None, description="AI gateway URL"
    )
    gateway_enabled: bool = DEFAULT_AI_GATEWAY_ENABLED
    gateway_weights: dict[str, int] = Field(default_factory=dict)
    gateway_concurrency: dict[str, int] = Field(default_factory=dict)
    portkey_url: HttpUrlStr | None = None
    api_base_url: Annotated[HttpUrlStr | None, Variable()] = Field(
        default=None, description="AI API base URL"
    )
    allow_private_network: Annotated[bool, Variable()] = Field(
        default=False, description="Permit private-IP network targets"
    )
    max_retries: Annotated[int, Variable()] = Field(
        description="Maximum retry count for AI requests upon response validation failure",
        default=DEFAULT_AI_MAX_RETRIES,
        ge=0,
    )
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
    tasks: Annotated[AITasksConfig, Variable(segment="TASK")] = AITasksConfig()
    rag: AIRAGConfig = AIRAGConfig()
    cache: AICacheConfig = AICacheConfig()
    task_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data.pop("durable", None)
            if "ollama_base_url" in data:
                val = data.pop("ollama_base_url")
                if "ollama_urls" not in data and val:
                    data["ollama_urls"] = [val] if isinstance(val, str) else val
        return data

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


class GitHubAppConfig(BaseModel):
    """The GitHub App that the roadmap Service and the cluster jobs act as (ADR 0015).

    Its private key is the managed credential `service.github_app.private_key`. A process acts as
    the App only when its environment holds that key, as Secret `devops/devops-cli` gives it to
    the cluster's pods; a workstation keeps the gh login of its person.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)

    app_id: Annotated[int | None, Variable()] = Field(
        default=None,
        gt=0,
        description="ID of the GitHub App that the roadmap Service and the cluster jobs act as",
    )
    installation_id: Annotated[int | None, Variable()] = Field(
        default=None,
        gt=0,
        description=(
            "ID of the App's installation on the account that owns the managed repositories"
        ),
    )
    slug: Annotated[str | None, Variable()] = Field(
        default=None,
        min_length=1,
        description="Slug of the GitHub App; its bot's login is `<slug>[bot]`",
    )
    token_repository: Annotated[str | None, Variable()] = Field(
        default=None,
        pattern=r"^[\w.-]+/[\w.-]+$",
        description=(
            "owner/name of the one repository that an installation token may name. Set on a "
            "runner Job by the Service, so a step cannot push to another repository. With it "
            "unset, a token covers every repository of the installation"
        ),
    )

    @field_validator("token_repository")
    @classmethod
    def _segments_are_names(cls, value: str | None) -> str | None:
        """No segment of `owner/name` is `.` or `..`: the pattern lets them through, and they
        are no repository."""
        if value is not None and {".", ".."} & set(value.split("/")):
            raise ValueError(f"{value!r} has a dot segment; use owner/name")
        return value

    @property
    def bot_login(self) -> str | None:
        """The login GitHub gives the App's bot, `<slug>[bot]`, or None without a slug."""
        return f"{self.slug}[bot]" if self.slug else None


class RoadmapStageConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)

    filter: Annotated[list[str], Variable()] = Field(
        description="The labels of the items that the stage job takes, as entries `family=value` over the families status, priority, type, value and effort: the values of one family are alternatives, and the families all apply; the job also takes Ready items only",
        default_factory=lambda: list(DEFAULT_ROADMAP_STAGE_FILTER),
        min_length=1,
    )
    limit: Annotated[int, Variable()] = Field(
        description="The most items that one run of the stage job takes",
        default=DEFAULT_ROADMAP_STAGE_LIMIT,
        ge=1,
    )
    step_tokens: Annotated[int, Variable()] = Field(
        description="The most tokens that the inputs of one implementation step may hold: the step's instructions, the AGENTS.md of the repository and the documents it routes the group to, the item, the change folder and the packed files of one task group; `devops roadmap stage` splits a task group over it",
        default=DEFAULT_ROADMAP_STAGE_STEP_TOKENS,
        ge=1000,
    )

    @field_validator("filter")
    @classmethod
    def _check_filter(cls, entries: list[str]) -> list[str]:
        for entry in entries:
            split_filter_entry(entry)
        return entries


class RoadmapImplementConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)

    in_runner: Annotated[bool, Variable()] = Field(
        description="Whether this process is the pod of a runner Job. Only then does `devops roadmap implement --confirm` run a step. The step's shell is no security boundary: the runner is the sandbox, with a narrow token and no other credential. The Service pod and a workstation keep this false",
        default=False,
    )
    repair_rounds: Annotated[int, Variable()] = Field(
        description="The most extra turns that one implementation step gives the agent after its first run: one for each failed `ruff`, `mypy` or hook of the project, and one for each time that tasks stay unticked. The same number bounds the fix steps that the scoped checks before a push cause. When no round is left, the step or the item stops. 0 gives the agent no extra turn",
        default=DEFAULT_ROADMAP_IMPLEMENT_REPAIR_ROUNDS,
        ge=0,
    )


class ServiceConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)

    repos: Annotated[list[str], Variable()] = Field(
        description="Target repository list for service mode", default_factory=list
    )
    github_app: GitHubAppConfig = Field(default_factory=GitHubAppConfig)
    poll_interval_seconds: Annotated[int, Variable()] = Field(
        description="Periodic polling interval for service mode in seconds",
        default=DEFAULT_SERVICE_POLL_INTERVAL_SECONDS,
        ge=60,
    )
    drain_timeout_seconds: Annotated[int, Variable()] = Field(
        description="Shutdown drain timeout for running service jobs in seconds",
        default=DEFAULT_SERVICE_DRAIN_TIMEOUT_SECONDS,
        gt=0,
    )
    github_requests_per_hour: Annotated[int, Variable()] = Field(
        description="The most GitHub requests the Service sends in one hour; a request that the last hour has no room for waits. The alert RoadmapServiceGitHubRequestsHigh follows this limit",
        default=DEFAULT_SERVICE_GITHUB_REQUESTS_PER_HOUR,
        gt=0,
    )
    model_call_concurrency: Annotated[int, Variable()] = Field(
        description="The most model calls the Service keeps in flight at once; a lane that waits does so in the Service, where no stall timer runs",
        default=DEFAULT_SERVICE_MODEL_CALL_CONCURRENCY,
        ge=1,
    )

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
                except json.JSONDecodeError:
                    pass
            return [str(item) for item in v if item]
        return []


class AlternativesConfig(BaseModel):
    """`devops roadmap alternatives` (#2650) and the Service's row of it (#2652)."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)

    limit: int = Field(
        description="Most items that one run of the alternatives check, or one Service round of it, checks",
        default=DEFAULT_ROADMAP_ALTERNATIVES_LIMIT,
        ge=1,
    )

    recheck_days: int = Field(
        description="Days after which an item's check for an open alternative tool is old and the item is checked again",
        default=DEFAULT_ROADMAP_ALTERNATIVES_RECHECK_DAYS,
        ge=1,
    )

    retry_days: int = Field(
        description="Days after a failed check of an item before the alternatives check takes the item again",
        default=DEFAULT_ROADMAP_ALTERNATIVES_RETRY_DAYS,
        ge=1,
    )


class RoadmapConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)

    alternatives: AlternativesConfig = Field(default_factory=AlternativesConfig)
    stage: RoadmapStageConfig = Field(default_factory=RoadmapStageConfig)
    implement: RoadmapImplementConfig = Field(default_factory=RoadmapImplementConfig)


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)

    dir: Annotated[Path, Variable()] = Field(
        description="Root data directory for local reviews, cache, logs, and artifacts (default: ./.data; outside devops-cli's own repository, ~/.local/share/devops-cli/.data for review data and a `devops review` command)",
        default_factory=lambda: DEFAULT_DATA_DIR,
    )
    analysis_dir: Annotated[Path, Variable()] = Field(
        description="Storage directory for pre-analysis metadata JSON files",
        default_factory=lambda: DEFAULT_ANALYSIS_DATA_DIR,
    )
    reviews_dir: Annotated[Path, Variable()] = Field(
        description="Storage directory for review session finding reports and artifacts",
        default_factory=lambda: DEFAULT_REVIEWS_DATA_DIR,
    )
    logs_dir: Annotated[Path, Variable()] = Field(
        description="Storage directory for CLI execution and SIEM audit logs",
        default_factory=lambda: DEFAULT_LOGS_DATA_DIR,
    )
    models_dir: Annotated[Path, Variable()] = Field(
        description="Storage directory for local model checkpoints and weights",
        default_factory=lambda: DEFAULT_MODELS_DATA_DIR,
    )
    cache_dir: Annotated[Path, Variable()] = Field(
        description="Storage directory for local response and retrieval cache",
        default_factory=lambda: DEFAULT_CACHE_DATA_DIR,
    )
    benchmarks_dir: Annotated[Path, Variable()] = Field(
        description="Storage directory for benchmark test runs and embedding leaderboard reports",
        default_factory=lambda: DEFAULT_BENCHMARKS_DATA_DIR,
    )
    rag_dir: Annotated[Path, Variable()] = Field(
        description="Storage directory for local vector embedding index cache and retrieval data",
        default_factory=lambda: DEFAULT_RAG_DATA_DIR,
    )
    samples_dir: Annotated[Path, Variable()] = Field(
        description="Storage directory for open-source sample repositories fetched at their pinned commits",
        default_factory=lambda: DEFAULT_SAMPLES_DATA_DIR,
    )
    runs_dir: Annotated[Path, Variable()] = Field(
        description="Storage directory for benchmark and evaluation run records, the run store's source of truth",
        default_factory=lambda: DEFAULT_RUNS_DATA_DIR,
    )
    tls_dir: Annotated[Path, Variable()] = Field(
        description="Storage directory for generated local CA and TLS certificates",
        default_factory=lambda: DEFAULT_TLS_DATA_DIR,
    )
    audit_log_path: Annotated[Path, Variable()] = Field(
        description="Path to structured audit JSONL log file",
        default_factory=lambda: DEFAULT_AUDIT_LOG_PATH,
    )
    feedback_dataset_path: Annotated[Path, Variable()] = Field(
        description="Path to feedback fine-tuning dataset JSONL file",
        default_factory=lambda: DEFAULT_FEEDBACK_DATASET_PATH,
    )

    @model_validator(mode="after")
    def _rebase_child_paths_if_custom_dir(self) -> DataConfig:
        if self.dir != DEFAULT_DATA_DIR:
            for field, default_val, rel_path in _DEFAULT_CHILD_DATA_PATHS:
                if getattr(self, field) == default_val:
                    setattr(self, field, self.dir / rel_path)
        return self


class FirecrawlConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True, hide_input_in_errors=True)

    api_key: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        frozen=False,
        hide_input_in_errors=True,
        validate_assignment=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """`Settings(...)` holds its arguments and the defaults, and reads no variable and no file.
        `load_settings` builds the settings from the sources that `setting_sources` declares."""
        return (init_settings,)

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
    roadmap: RoadmapConfig = RoadmapConfig()
    firecrawl: FirecrawlConfig = FirecrawlConfig()
    # The values that `load_settings` returned, so `save_settings` writes only the keys that
    # changed after the load (#1999). Settings made in code have none, and start from the defaults.
    _loaded: dict[str, Any] | None = PrivateAttr(default=None)


def _key_field(key: str) -> FieldInfo:
    """The settings field that the dotted `key` of a declared setting names."""
    model: type[BaseModel] = Settings
    *path, name = key.split(".")
    for part in path:
        model = typing.cast(type[BaseModel], model.model_fields[part].annotation)
    return model.model_fields[name]


def setting_default(key: str) -> Any:
    """The default that the settings field of the dotted `key` declares.

    A module outside `config/` reads a setting from the loaded settings. It reads this only where
    no settings are loaded, so a config file or a variable that sets the key is never ignored
    where the settings are at hand (#2447).
    """
    return _key_field(key).get_default(call_default_factory=True)


def _nested(values: dict[str, Any], key: str, value: Any) -> None:
    """Put `value` at the dotted `key` of the nested mapping `values`."""
    *path, name = key.split(".")
    for part in path:
        values = values.setdefault(part, {})
    values[name] = value


class SettingVariables(PydanticBaseSettingsSource):
    """The settings that their variables set (`config/env.py`), as a settings source.

    An empty variable sets nothing. A list setting takes a JSON list or comma-separated values.
    `DEVOPS_CLI_DATA_DIR` also sets each data path that no variable of its own sets, under that
    directory, so the data paths of a config file do not apply.
    """

    def __init__(self, settings_cls: type[BaseSettings], keys: Iterable[str] | None = None) -> None:
        super().__init__(settings_cls)
        variables = setting_variables()
        # The variable that gave each key, so a value that does not validate names its variable.
        self.variables_set: dict[str, str] = {}
        self._values: dict[str, Any] = {}
        for key in variables if keys is None else keys:
            value = os.environ.get(variables[key])
            if value:
                is_list = _is_list_annotation(_key_field(key).annotation)
                self._set(key, _coerce_setting_value(value, is_list), variables[key])
        data_dir = self._values.get("data", {}).get("dir")
        if data_dir:
            for field_name, _default, relative in _DEFAULT_CHILD_DATA_PATHS:
                if f"data.{field_name}" not in self.variables_set:
                    self._set(
                        f"data.{field_name}", Path(data_dir) / relative, variables["data.dir"]
                    )

    def _set(self, key: str, value: Any, variable: str) -> None:
        _nested(self._values, key, value)
        self.variables_set[key] = variable

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return self._values.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return copy.deepcopy(self._values)


class MappingSource(PydanticBaseSettingsSource):
    """The settings that one mapping holds, as a settings source: a config file as one load read
    it, or a fixed layer."""

    def __init__(self, settings_cls: type[BaseSettings], values: dict[str, Any]) -> None:
        super().__init__(settings_cls)
        self._values = values

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return self._values.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._values


_FileStamp = tuple[str, int, int]
_ConfigCacheEntry = tuple[tuple[_FileStamp, _FileStamp], "ConfigLayers"]

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


# The errors of `yaml.safe_load` and of the UTF-8 decode, from the constructors of PyYAML's
# SafeConstructor: `UnicodeDecodeError` is a `ValueError`, and `KeyError` and `IndexError` are
# `LookupError`s. `tests/config/test_config_file_that_is_not_yaml.py` holds a file for each.
_YAML_LOAD_ERRORS: tuple[type[Exception], ...] = (
    yaml.YAMLError,
    ValueError,
    LookupError,
    AttributeError,
    RecursionError,
)


def _read_config_file(path: Path) -> Any:
    """The YAML document of the config file `path`, or `{}` for an empty file.

    A file that is not valid YAML raises ConfigurationError that names the file, the type of the
    error, and its line and column when the error has a mark. The error of PyYAML quotes the line
    where the parser stopped, and the `buffer` of its mark holds the full text of the file, which
    can hold a credential. The safe loader also raises `ValueError`, `KeyError`, `IndexError` or
    `AttributeError` with the value in the message for a tagged value that it cannot build, such
    as `!!int <text>`, and `RecursionError` for a document that nests too deep. The decode of a
    file that is not UTF-8 raises `UnicodeDecodeError`, whose `object` holds the bytes of the
    file. Each of these errors gives the same message, which holds no text of the file, and the
    error is raised after the `except` block: it has no cause and no context that holds the
    first error (#1468). An `OSError` names only the file and is not a YAML problem, so it goes
    up as it is.
    """
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except _YAML_LOAD_ERRORS as exc:
        error_type, location = type(exc).__name__, _yaml_error_location(exc)
    raise ConfigurationError(
        ERRORS.config.not_yaml.format(path=path, error_type=error_type, location=location)
    )


def _yaml_error_location(exc: Exception) -> str:
    """` at line <n>, column <n>` where PyYAML stopped, counted from 1, or "" with no mark."""
    mark = exc.problem_mark if isinstance(exc, yaml.MarkedYAMLError) else None
    if mark is None:
        return ""
    return ERRORS.config.not_yaml_location.format(line=mark.line + 1, column=mark.column + 1)


def config_layer_paths() -> tuple[Path, Path | None]:
    """The config files that the settings read: the global config file, and the project config
    file or None when there is no project file. A value in the project file wins over the global
    file (`setting_sources`).

    `load_settings` reads these files, and `devops config audit-keys` scans them, so a file that
    gives a value to the settings is also a file that the audit scans (#2426). A file need not
    exist.
    """
    return CONFIG_PATH, _find_project_config_path()


class ConfigLayers(typing.NamedTuple):
    """The config files of one load, each as its file holds it."""

    project_path: Path | None
    project: dict[str, Any]
    global_config: dict[str, Any]


def _read_config_mapping(path: Path | None) -> dict[str, Any]:
    """The mapping of the config file `path`; `{}` when it is absent or empty."""
    if path is None or not path.exists():
        return {}
    data = _read_config_file(path)
    if not isinstance(data, dict):
        raise ConfigurationError(ERRORS.config.not_mapping.format(path=path))
    return data


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    """`values` without the keys whose value is None, at any depth: a project file's null is no
    value, so the global file's value of the key stays."""
    return {
        key: _without_none(value) if isinstance(value, dict) else value
        for key, value in values.items()
        if value is not None
    }


def _config_layers() -> ConfigLayers:
    """Return the config files, re-reading them only when one of them changed.

    Settings are consulted from per-request paths, yet each call otherwise walked the
    directory tree hunting for a project config and re-parsed both YAML layers to arrive
    at the identical mapping. Reuse is conditional on the files that supplied the values
    still carrying the stamp they had when parsed, so an edit made by any process is
    honoured on the next call rather than a snapshot living for the process lifetime.
    Only the discovery walk is taken on trust: a project config file created after the
    first load is picked up once the cache is reset, because a stamp of a file that did
    not exist cannot report where a new one appeared.

    The caller receives a copy, since the settings built from these mappings are mutable and
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
        cached_stamps, cached_layers = entry
        if cached_stamps == (_file_stamp(CONFIG_PATH), _file_stamp(cached_layers.project_path)):
            return copy.deepcopy(cached_layers)

    # Stamped before the read, so a write that races the read leaves a stamp that looks
    # older than the content held -- which costs a re-read, never a stale answer.
    global_path, project_path = config_layer_paths()
    stamps = (_file_stamp(global_path), _file_stamp(project_path))
    layers = ConfigLayers(
        project_path,
        _without_none(_read_config_mapping(project_path)),
        _read_config_mapping(global_path),
    )
    if _stamps_are_settled(stamps):
        with _CONFIG_CACHE_LOCK:
            # A different key means a different working directory or configuration path,
            # which strands the previous entry; keeping it would grow without bound.
            _CONFIG_CACHE.clear()
            _CONFIG_CACHE[cache_key] = (stamps, copy.deepcopy(layers))
    return layers


def setting_sources(layers: ConfigLayers) -> tuple[PydanticBaseSettingsSource, ...]:
    """The order in which every setting resolves, the first source that holds it winning: its
    variable, then the project config file, then the global config file. A setting that no source
    holds keeps the default of its field. A credential resolves in its own chain, which
    `security.secrets.build_default_resolver` declares: the keyring, Vault, its variable, then the
    config file."""
    return (
        SettingVariables(Settings),
        MappingSource(Settings, layers.project),
        MappingSource(Settings, layers.global_config),
    )


def _variable_error(
    exc: ValidationError, sources: Iterable[PydanticBaseSettingsSource]
) -> ConfigurationError | None:
    """The error of the first value that does not validate and that a variable gave, if one did."""
    variables = next((s.variables_set for s in sources if isinstance(s, SettingVariables)), {})
    for error in exc.errors(include_url=False, include_input=False):
        location = ".".join(str(part) for part in error["loc"])
        key = next((k for k in variables if location == k or location.startswith(f"{k}.")), None)
        if key is not None:
            reason = error["msg"].removeprefix("Value error, ")
            return ConfigurationError(
                f"Environment variable {variables[key]} cannot set {key}: {location}: {reason}",
                key=key,
            )
    return None


def _settings_from(sources: tuple[PydanticBaseSettingsSource, ...]) -> Settings:
    """The settings that `sources` give, the first source that holds a key winning."""
    try:
        return Settings(_build_sources=(sources, {}))
    except ValidationError as exc:
        refused = _variable_error(exc, sources)
        if refused is None:
            raise
        raise refused from exc


def reset_settings_cache() -> None:
    """Discard parsed configuration so the next load reads the files from disk again."""
    with _CONFIG_CACHE_LOCK:
        _CONFIG_CACHE.clear()


def load_settings() -> Settings:
    """Load the settings from the sources that `setting_sources` declares.

    While a command that reads a tree it does not own runs, such as a review, from a repository
    other than devops-cli's own, the project layer is only the file `DEVOPS_CLI_CONFIG` names
    (`_find_project_config_path`, #972). The variables stay outside the cache of the files: they
    cost microseconds to read, and a variable exported after the first load must still take effect.
    """
    layers = _config_layers()
    try:
        settings = _settings_from(setting_sources(layers))
    except ValidationError as exc:
        # A key that a section refuses gets its file, its line and the command that removes it,
        # which the error of pydantic does not give (#2201).
        from devops_cli.config import unknown_keys

        refused = unknown_keys.refused_keys(exc)
        if not refused:
            raise
        raise unknown_keys.unknown_keys_error(
            refused,
            (layers.project_path, CONFIG_PATH),
            active=layers.project_path or CONFIG_PATH,
        ) from exc
    settings._loaded = settings.model_dump(mode="json")
    return settings


def telemetry_from_environment() -> TelemetryConfig:
    """The telemetry section from its registered variables alone, for settings that cannot load.

    An unreadable configuration layer, or a registered variable that cannot apply, may be the one
    turning export off, so export stays off unless `DEVOPS_CLI_TELEMETRY_ENABLED` turns it on: an
    opt-out never fails open to the default (#956).
    """
    sources = (
        SettingVariables(Settings, _TELEMETRY_ENV_OPTIONS),
        MappingSource(Settings, {"telemetry": {"enabled": False}}),
    )
    try:
        return _settings_from(sources).telemetry
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


def _write_content(
    dest_path: Path,
    previous: bytes | None,
    content: bytes,
    redact: Collection[tuple[str, ...]] = (),
) -> Path | None:
    """Write `content` into `dest_path` when it differs from the `previous` content: copy the file
    first, and then record the write in the audit log. Return the copy, or None when the write
    changes nothing or the file did not exist. `redact` names the key paths of the credentials
    that the write removes: no copy of the file holds their values afterwards (#2645)."""
    from devops_cli.config import write_history

    if content == previous:
        return None
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    backup = write_history.back_up(dest_path, redact)
    tmp = dest_path.with_suffix(".yaml.tmp")
    tmp.write_bytes(content)
    mode = stat.S_IMODE(dest_path.stat().st_mode) if dest_path.is_file() else 0o600
    os.chmod(tmp, mode)
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
    as a save does. A copy shows the value of each credential that the removal takes out of the
    file, and of the same credential in each older copy, as `***REDACTED***`, so the removal leaves
    no copy that holds the credential (#2645). A dry run returns the same removal, with no copy,
    and writes nothing. A key that the file does not hold raises ConfigurationError, and the file
    stays as it is.
    """
    import difflib

    from devops_cli.config import round_trip, write_history
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
        credentials = write_history.credential_paths(previous, path, _SECRET_FIELDS)
        backup = _write_content(dest_path, previous, content.encode("utf-8"), credentials)
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

    ref = build_secret_registry()[option]
    # Bind the caller's settings so configuration-sourced values reflect this call, not a
    # snapshot captured when the process-wide resolver was first constructed.
    return get_resolver().resolve(ref, settings_source=lambda: settings)


def get_grafana_token(settings: Settings) -> str | None:
    """Resolve the Grafana API token, rejecting masked placeholder values."""
    token = _resolve("grafana.token", settings)
    return token if token and not token.startswith("*") else None


def get_grafana_password(settings: Settings) -> str | None:
    """Resolve the Grafana account password."""
    return _resolve("grafana.password", settings)


def get_argocd_token(settings: Settings) -> str | None:
    """Resolve the ArgoCD API token, rejecting masked placeholder values."""
    token = _resolve("argocd.token", settings)
    # A masked value indicates a redacted export was re-imported, not a usable token.
    return token if token and not token.startswith("*") else None


def get_argocd_password(settings: Settings) -> str | None:
    """Resolve the ArgoCD account password."""
    return _resolve("argocd.password", settings)


def get_ai_api_key(settings: Settings) -> str | None:
    """Resolve the AI provider API key."""
    return _resolve("ai.api_key", settings)


def get_qdrant_api_key(settings: Settings) -> str | None:
    """Resolve the Qdrant API key."""
    return _resolve("qdrant.api_key", settings)


def get_valkey_password(settings: Settings) -> str | None:
    """Resolve the Valkey password."""
    return _resolve("valkey.password", settings)


def get_runs_index_password(settings: Settings) -> str | None:
    """Resolve the password of the Valkey holding the shared run index."""
    return _resolve("runs.index_password", settings)


def get_gitea_admin_password(settings: Settings) -> str | None:
    """Resolve the password of Gitea's admin user."""
    return _resolve("gitea.admin_password", settings)


def get_logfire_token(settings: Settings) -> str | None:
    """Resolve the Logfire telemetry write token."""
    return _resolve("telemetry.logfire_token", settings)


def get_cloudflare_api_token(settings: Settings) -> str | None:
    """Resolve the Cloudflare API token."""
    return _resolve("cloudflare.api_token", settings)


def get_service_webhook_secrets(settings: Settings) -> str | None:
    """Resolve the JSON mapping of repo to webhook secret."""
    return _resolve("service.webhook_secrets", settings)


def get_firecrawl_api_key(settings: Settings | None = None) -> str | None:
    """Resolve the Firecrawl web search API key."""
    active_settings = settings or load_settings()
    return _resolve("firecrawl.api_key", active_settings)


def _canonical_key(key: str) -> str:
    """The settings key that a dotted key names: `otel.<field>` names `telemetry.<field>`."""
    return "telemetry." + key[5:] if key.startswith("otel.") else key


def dotted_get(settings: Settings, key: str) -> Any:
    """Get a config value by dotted key, e.g. 'github.default_org'."""
    return operator.attrgetter(_canonical_key(key))(settings)


def _field_keys(model: type[BaseModel], prefix: str = "") -> Iterator[str]:
    """The dotted key of each field of `model` that holds a value, in its sections at any depth."""
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            yield from _field_keys(annotation, f"{prefix}{name}.")
        else:
            yield f"{prefix}{name}"


def _config_keys() -> frozenset[str]:
    """Each key that `devops config set` takes: a settings field that holds a value, or a
    credential. Some credentials, such as `grafana.token`, have no settings field."""
    return frozenset(_field_keys(Settings)) | _SECRET_FIELDS


def is_config_key(key: str) -> bool:
    """Whether the dotted `key` names a settings field that holds a value, or a credential.

    A section, such as `ai` or `ai.tasks.chat`, holds no value of its own, so it is no config key.
    """
    return _canonical_key(key) in _config_keys()


def similar_config_keys(key: str) -> list[str]:
    """The config keys whose names are nearest to the dotted `key`, the nearest first."""
    import difflib

    return difflib.get_close_matches(_canonical_key(key), _config_keys())


def _coerce_setting_value(new_value: Any, is_list_field: bool) -> Any:
    """Split comma-separated strings for list fields, leaving other values for Pydantic validation."""
    if not (is_list_field and isinstance(new_value, str)):
        return new_value
    trimmed = new_value.strip()
    if trimmed.startswith("[") and trimmed.endswith("]"):
        parsed = _json_list(trimmed)
        if parsed is not None:
            return [str(item) for item in parsed if item]
    return [v.strip() for v in trimmed.split(",") if v.strip()]


def _json_list(text: str) -> list[Any] | None:
    """The JSON array that `text` holds, or None when it holds no JSON or no array."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def dotted_set(settings: Settings, key: str, value: Any) -> None:
    """Set a config value by dotted key, at any depth. Secret keys go to the OS keyring.

    `ai.tasks.chat.model` walks the nested sections; a key naming no field raises
    ConfigurationError rather than setting nothing.
    """
    if key in _SECRET_FIELDS:
        store_keyring_secret(_KEYRING_KEYS[key], value)
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
