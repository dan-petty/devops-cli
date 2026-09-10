"""Configuration settings resolution, Pydantic models, and keyring helpers."""

from __future__ import annotations

import operator
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from devops_cli.config import options as opt
from devops_cli.config.constants import (
    CONST_CONFIG_PATH as CONFIG_PATH,
)
from devops_cli.config.constants import (
    CONST_KEYRING_SERVICE as KEYRING_SERVICE,
)
from devops_cli.config.constants import (
    CONST_PROJECT_CONFIG_ENV as PROJECT_CONFIG_ENV,
)
from devops_cli.config.constants import (
    CONST_PROJECT_CONFIG_FILENAME as PROJECT_CONFIG_FILENAME,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_CONTEXT_WINDOW,
    DEFAULT_AI_DURABLE_ENGINE,
    DEFAULT_AI_DURABLE_STORE_PATH,
    DEFAULT_AI_DURABLE_TASK_QUEUE,
    DEFAULT_AI_DURABLE_WORKFLOW_PREFIX,
    DEFAULT_AI_MAX_RETRIES,
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROVIDER,
    DEFAULT_AI_REASONING_EFFORT,
    DEFAULT_AI_TEMPERATURE,
    DEFAULT_AI_TOP_P,
    DEFAULT_ANALYSIS_DATA_DIR,
    DEFAULT_AUDIT_LOG_PATH,
    DEFAULT_BENCHMARKS_DATA_DIR,
    DEFAULT_CACHE_DATA_DIR,
    DEFAULT_DATA_DIR,
    DEFAULT_FEEDBACK_DATASET_PATH,
    DEFAULT_JAEGER_URL,
    DEFAULT_LLM_CACHE_DATA_DIR,
    DEFAULT_LLM_CACHE_ENABLED,
    DEFAULT_LLM_CACHE_MAX_ENTRIES,
    DEFAULT_LLM_CACHE_TTL_SECONDS,
    DEFAULT_LOGS_DATA_DIR,
    DEFAULT_MODELS_DATA_DIR,
    DEFAULT_OLLAMA_MAX_PARALLEL,
    DEFAULT_OLLAMA_URLS,
    DEFAULT_OTEL_ENDPOINT,
    DEFAULT_QDRANT_URL,
    DEFAULT_RAG_CHUNK_OVERLAP,
    DEFAULT_RAG_CHUNK_SIZE,
    DEFAULT_RAG_DATA_DIR,
    DEFAULT_RAG_EMBEDDING_MODEL,
    DEFAULT_RAG_EMBEDDING_TIMEOUT,
    DEFAULT_RAG_EMBEDDING_URL,
    DEFAULT_RAG_SCORE_THRESHOLD,
    DEFAULT_RAG_TOP_K,
    DEFAULT_REPOS_BASE_DIR,
    DEFAULT_REVIEWS_DATA_DIR,
    DEFAULT_SSH_KEY_DIR,
    DEFAULT_SSH_KEY_PREFIX,
    DEFAULT_SSH_ROTATION_DAYS,
    DEFAULT_TLS_DATA_DIR,
    DEFAULT_WORKSPACE_FILE,
)
from devops_cli.config.env import OPTION_TO_ENV_VAR
from devops_cli.exceptions import ConfigurationError

_SECRET_FIELDS: frozenset[str] = opt.SECRET_CONFIG_OPTIONS
_KEYRING_KEYS: dict[str, str] = opt.KEYRING_KEYS


class SecretStorageError(RuntimeError):
    """Raised when a secret cannot be stored in the configured keyring backend."""


def _ensure_keyring_backend() -> bool:
    """Ensure keyring has a usable, encrypted backend and reject unencrypted backends."""
    import keyring
    from keyring.backends.fail import Keyring as FailKeyring

    backend = keyring.get_keyring()
    if backend is None or isinstance(backend, FailKeyring):
        return False

    # Check priority and reject known unencrypted/insecure backends
    backend_class_name = type(backend).__name__
    backend_module = type(backend).__module__

    if "Plaintext" in backend_class_name or "keyrings.alt" in backend_module:
        return False

    priority = getattr(backend, "priority", 0)
    return bool(priority > 0)


class GitHubConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    default_org: str | None = None


class SSHConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    key_dir: Path = DEFAULT_SSH_KEY_DIR
    key_prefix: str | None = DEFAULT_SSH_KEY_PREFIX
    rotation_days: int = DEFAULT_SSH_ROTATION_DAYS


class ReposConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    base_dir: Path = DEFAULT_REPOS_BASE_DIR


class WorkspaceConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    file: Path = DEFAULT_WORKSPACE_FILE


class GrafanaConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    url: str | None = None


class PrometheusConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    url: str | None = None


class ArgoCDConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    url: str | None = None


class QdrantConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    url: str | None = DEFAULT_QDRANT_URL
    collection_prefix: str = "devops"
    api_key: str | None = None


class ValkeyConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    host: str = "localhost"
    port: int = 6379
    password: str | None = None
    db: int = 0
    timeout: float = 2.0


class JaegerConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    url: str | None = DEFAULT_JAEGER_URL


class TelemetryConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    enabled: bool = True
    endpoint: str = DEFAULT_OTEL_ENDPOINT
    logfire: bool = False
    logfire_token: str | None = None
    logfire_send_to_logfire: bool | str = "if-token-present"


class AIRAGConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    enabled: bool = True
    embedding_model: str = DEFAULT_RAG_EMBEDDING_MODEL
    embedding_url: str | None = DEFAULT_RAG_EMBEDDING_URL
    embedding_timeout: float = DEFAULT_RAG_EMBEDDING_TIMEOUT
    top_k: int = DEFAULT_RAG_TOP_K
    score_threshold: float = DEFAULT_RAG_SCORE_THRESHOLD
    chunk_size: int = DEFAULT_RAG_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_RAG_CHUNK_OVERLAP


class AICacheConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    enabled: bool = DEFAULT_LLM_CACHE_ENABLED
    backend: str = "file"  # "file" | "valkey" | "memory"
    dir: Path = DEFAULT_LLM_CACHE_DATA_DIR
    ttl_seconds: int = DEFAULT_LLM_CACHE_TTL_SECONDS
    max_entries: int = DEFAULT_LLM_CACHE_MAX_ENTRIES
    append_cache: bool = False


class AIDurableConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    engine: str = DEFAULT_AI_DURABLE_ENGINE
    store_path: Path = Field(default_factory=lambda: DEFAULT_AI_DURABLE_STORE_PATH)
    task_queue: str = DEFAULT_AI_DURABLE_TASK_QUEUE
    workflow_id_prefix: str = DEFAULT_AI_DURABLE_WORKFLOW_PREFIX


class AITaskOverride(BaseModel):
    """Per-task model/server override; unset fields fall back to the parent AIConfig."""

    model_config = ConfigDict(frozen=False)
    provider: str | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    context_window: int | None = None
    num_ctx: int | None = None
    max_tokens: int | None = None
    ollama_urls: list[str] | None = None
    ollama_max_parallel: int | None = None
    api_base_url: str | None = None
    max_retries: int | None = None


class AITasksConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    chat: AITaskOverride = AITaskOverride()
    metadata: AITaskOverride = AITaskOverride()
    analysis: AITaskOverride = AITaskOverride()
    compose: AITaskOverride = AITaskOverride()
    embedding: AITaskOverride = AITaskOverride()


class AIConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    provider: str = DEFAULT_AI_PROVIDER  # ollama | claude | copilot | openai
    model: str = DEFAULT_AI_MODEL
    reasoning_effort: str | None = DEFAULT_AI_REASONING_EFFORT
    temperature: float = DEFAULT_AI_TEMPERATURE
    top_p: float = DEFAULT_AI_TOP_P
    context_window: int = DEFAULT_AI_CONTEXT_WINDOW
    num_ctx: int | None = None
    max_tokens: int | None = None
    ollama_urls: list[str] = Field(default_factory=lambda: list(DEFAULT_OLLAMA_URLS))
    ollama_max_parallel: int = DEFAULT_OLLAMA_MAX_PARALLEL
    api_base_url: str | None = None
    allow_private_network: bool = False
    max_retries: int = DEFAULT_AI_MAX_RETRIES
    tasks: AITasksConfig = AITasksConfig()
    rag: AIRAGConfig = AIRAGConfig()
    cache: AICacheConfig = AICacheConfig()
    durable: AIDurableConfig = AIDurableConfig()

    @model_validator(mode="before")
    @classmethod
    def _migrate_append_cache(cls, data: Any) -> Any:
        if isinstance(data, dict) and "append_cache" in data:
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
            return list(DEFAULT_OLLAMA_URLS)

        cleaned: list[str] = []
        for u in self.ollama_urls:
            raw = (u or "").strip().rstrip("/")
            if not raw:
                continue
            cleaned.append(raw if raw.startswith(("http://", "https://")) else f"http://{raw}")
        return cleaned or list(DEFAULT_OLLAMA_URLS)

    def for_task(self, task: str) -> AIConfig:
        """Return a copy with task-specific overrides from ai.tasks.<task> applied."""
        override: AITaskOverride = getattr(self.tasks, task, AITaskOverride())
        updates = {
            k: v
            for k, v in {
                "provider": override.provider,
                "model": override.model,
                "reasoning_effort": override.reasoning_effort,
                "temperature": override.temperature,
                "top_p": override.top_p,
                "context_window": override.context_window,
                "num_ctx": override.num_ctx,
                "max_tokens": override.max_tokens,
                "ollama_urls": override.ollama_urls,
                "ollama_max_parallel": override.ollama_max_parallel,
                "api_base_url": override.api_base_url,
                "max_retries": override.max_retries,
            }.items()
            if v is not None
        }
        return self.model_copy(update=updates) if updates else self


_DEFAULT_CHILD_DATA_PATHS: tuple[tuple[str, Path, Path], ...] = (
    ("analysis_dir", DEFAULT_ANALYSIS_DATA_DIR, Path("analysis")),
    ("reviews_dir", DEFAULT_REVIEWS_DATA_DIR, Path("reviews")),
    ("logs_dir", DEFAULT_LOGS_DATA_DIR, Path("logs")),
    ("models_dir", DEFAULT_MODELS_DATA_DIR, Path("models")),
    ("cache_dir", DEFAULT_CACHE_DATA_DIR, Path("cache")),
    ("benchmarks_dir", DEFAULT_BENCHMARKS_DATA_DIR, Path("benchmarks")),
    ("rag_dir", DEFAULT_RAG_DATA_DIR, Path("rag")),
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
    "tls_dir": DEFAULT_TLS_DATA_DIR,
    "audit_log_path": DEFAULT_AUDIT_LOG_PATH,
    "feedback_dataset_path": DEFAULT_FEEDBACK_DATASET_PATH,
}


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dir: Path = Field(default_factory=lambda: DEFAULT_DATA_DIR)
    analysis_dir: Path = Field(default_factory=lambda: DEFAULT_ANALYSIS_DATA_DIR)
    reviews_dir: Path = Field(default_factory=lambda: DEFAULT_REVIEWS_DATA_DIR)
    logs_dir: Path = Field(default_factory=lambda: DEFAULT_LOGS_DATA_DIR)
    models_dir: Path = Field(default_factory=lambda: DEFAULT_MODELS_DATA_DIR)
    cache_dir: Path = Field(default_factory=lambda: DEFAULT_CACHE_DATA_DIR)
    benchmarks_dir: Path = Field(default_factory=lambda: DEFAULT_BENCHMARKS_DATA_DIR)
    rag_dir: Path = Field(default_factory=lambda: DEFAULT_RAG_DATA_DIR)
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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DEVOPS_CLI_",
        env_nested_delimiter="__",
        extra="ignore",
        frozen=False,
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
    jaeger: JaegerConfig = JaegerConfig()
    telemetry: TelemetryConfig = TelemetryConfig()
    ai: AIConfig = AIConfig()
    data: DataConfig = DataConfig()


_EPHEMERAL_CI_SECRETS: dict[str, str] = {}


def _keyring_get(key: str) -> str | None:
    import keyring
    from keyring.errors import NoKeyringError

    if key in _EPHEMERAL_CI_SECRETS:
        return _EPHEMERAL_CI_SECRETS[key]

    if not _ensure_keyring_backend():
        return None

    try:
        return keyring.get_password(KEYRING_SERVICE, key)
    except NoKeyringError:
        return None
    except Exception:
        return None


def _keyring_has(key: str) -> bool:
    """Check whether a secret key exists in OS keyring or ephemeral store."""
    import keyring
    from keyring.errors import NoKeyringError

    if key in _EPHEMERAL_CI_SECRETS:
        return True

    if not _ensure_keyring_backend():
        return False

    try:
        val = keyring.get_password(KEYRING_SERVICE, key)
        return bool(val is not None)
    except NoKeyringError, Exception:
        return False


def _keyring_set(key: str, value: str) -> None:
    import os

    import keyring
    from keyring.errors import NoKeyringError

    if os.environ.get("DEVOPS_CLI_HEADLESS_AUTH", "").lower() in ("true", "1", "yes"):
        _EPHEMERAL_CI_SECRETS[key] = value
        return

    if not _ensure_keyring_backend():
        _EPHEMERAL_CI_SECRETS[key] = value
        return

    try:
        keyring.set_password(KEYRING_SERVICE, key, value)
    except NoKeyringError:
        _EPHEMERAL_CI_SECRETS[key] = value
    except Exception as exc:
        raise SecretStorageError(f"Failed to store secret in keyring: {exc}") from exc


def get_keyring_secret(key: str) -> str | None:
    """Public helper to retrieve a secret from OS Keyring or ephemeral store."""
    return _keyring_get(key)


def set_keyring_secret(key: str, value: str) -> bool:
    """Public helper to store a secret in OS Keyring or ephemeral store."""
    try:
        _keyring_set(key, value)
        return True
    except Exception:
        return False


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Merge override into base in-place; override wins on conflict, None skipped."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        elif value is not None:
            base[key] = value


def _apply_env_overrides(settings: Settings) -> None:
    """Allow devcontainer and shell environment variables to override file config."""
    env_data_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    if env_data_dir:
        settings.data.dir = Path(env_data_dir)

    for option_key, env_var in OPTION_TO_ENV_VAR.items():
        if option_key in _SECRET_FIELDS:
            continue
        env_value = os.environ.get(env_var)
        if env_value in (None, ""):
            continue
        try:
            dotted_set(settings, option_key, env_value)
        except AttributeError, ValueError:
            # Ignore invalid or unknown env overrides and keep existing settings.
            continue


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


def load_settings() -> Settings:
    """Load settings: global config → project config → env vars (each layer wins)."""
    raw: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}

    # DEVOPS_CLI_CONFIG env var or local/devcontainer project config lookup.
    project_path = _find_project_config_path()
    if project_path and project_path.exists():
        project_raw: dict[str, Any] = yaml.safe_load(project_path.read_text(encoding="utf-8")) or {}
        _deep_merge(raw, project_raw)

    settings = Settings.model_validate(raw)
    _apply_env_overrides(settings)

    raw_data = raw.get("data", {}) if isinstance(raw.get("data"), dict) else {}
    settings.data = _resolve_data_config(raw_data, settings.data.dir)

    return settings


def _find_project_config_path(base_dir: Path | None = None) -> Path | None:
    """Locate candidate project/devcontainer config file from env, base_dir, or ancestor directories."""
    env_config = os.environ.get(PROJECT_CONFIG_ENV)
    if env_config:
        env_path = Path(env_config)
        if env_path.is_file():
            return env_path.resolve()

    candidate_names = (
        PROJECT_CONFIG_FILENAME,
        f".devcontainer/{PROJECT_CONFIG_FILENAME}",
        f".devops/{PROJECT_CONFIG_FILENAME}",
        ".devops.yaml",
        ".devcontainer/.devops.yaml",
    )
    start_dir = (base_dir or Path.cwd()).resolve()
    for d in (start_dir, *start_dir.parents):
        for name in candidate_names:
            p = d / name
            if p.is_file():
                return p.resolve()
        if (d / ".git").exists() or (d / ".devcontainer").exists():
            break
    return None


def get_active_config_path(base_dir: Path | None = None) -> Path:
    """Return active config file path (DEVOPS_CLI_CONFIG > project config > ~/.config)."""
    found = _find_project_config_path(base_dir=base_dir)
    return found if found is not None else CONFIG_PATH


def save_settings(settings: Settings, target_path: Path | None = None) -> None:
    """Persist settings to config YAML (secrets stay in keyring only)."""
    dest_path = target_path or get_active_config_path()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    data = settings.model_dump(mode="json", exclude_none=True)
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    tmp = dest_path.with_suffix(".yaml.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, dest_path)


# NOTE (Design Justification - AGENTS.md §4): Secret storage prioritizes OS keyring integration
# (_keyring_get/_keyring_set) while environment variable overrides (e.g., DEVOPS_CLI_GITHUB_TOKEN)
# serve as an intentional fallback mechanism for non-interactive CI environments.
def get_github_token(settings: Settings) -> str | None:
    return _keyring_get(_KEYRING_KEYS[opt.GITHUB_TOKEN]) or _github_cli_token()


def _github_cli_token() -> str | None:
    """Return token from `gh auth token` when GitHub CLI is authenticated."""
    from devops_cli.core.process import run_subprocess

    try:
        result = run_subprocess(["gh", "auth", "token"], quiet=True, timeout=5.0)
    except FileNotFoundError, OSError, subprocess.SubprocessError:
        return None

    if result.returncode != 0:
        return None

    token = result.stdout.strip()
    return token or None


def get_grafana_token(settings: Settings) -> str | None:
    return _keyring_get(_KEYRING_KEYS[opt.GRAFANA_TOKEN])


def get_grafana_password(settings: Settings) -> str | None:
    return _keyring_get(_KEYRING_KEYS[opt.GRAFANA_PASSWORD])


def get_argocd_token(settings: Settings) -> str | None:
    token = _keyring_get(_KEYRING_KEYS[opt.ARGOCD_TOKEN]) or os.getenv("DEVOPS_CLI_ARGOCD_TOKEN")
    if token and not token.startswith("*"):
        return token
    return None


def get_argocd_password(settings: Settings) -> str | None:
    return _keyring_get(_KEYRING_KEYS[opt.ARGOCD_PASSWORD])


def get_ai_api_key(settings: Settings) -> str | None:
    return _keyring_get(_KEYRING_KEYS[opt.AI_API_KEY])


def get_qdrant_api_key(settings: Settings) -> str | None:
    return _keyring_get(_KEYRING_KEYS[opt.QDRANT_API_KEY]) or settings.qdrant.api_key


def get_valkey_password(settings: Settings) -> str | None:
    return _keyring_get(_KEYRING_KEYS[opt.VALKEY_PASSWORD]) or settings.valkey.password


def get_logfire_token(settings: Settings) -> str | None:
    return (
        _keyring_get(_KEYRING_KEYS[opt.TELEMETRY_LOGFIRE_TOKEN])
        or os.getenv("DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN")
        or getattr(settings.telemetry, "logfire_token", None)
        or os.getenv("LOGFIRE_TOKEN")
    )


def get_llm_client(task: str | None = None) -> Any:
    """Instantiate a configured LLMClient instance based on active application settings."""
    from devops_cli.ai.client import LLMClient

    settings = load_settings()
    config = settings.ai.for_task(task) if task else settings.ai
    api_key = get_ai_api_key(settings)
    return LLMClient(config, api_key=api_key)


def dotted_get(settings: Settings, key: str) -> Any:
    """Get a config value by dotted key, e.g. 'github.default_org'."""
    normalized_key = "telemetry." + key[5:] if key.startswith("otel.") else key
    return operator.attrgetter(normalized_key)(settings)


def _coerce_setting_value(current_val: Any, new_value: Any, is_list_field: bool) -> Any:
    """Coerce string or raw setting input into target type based on current field schema."""
    if isinstance(current_val, Path):
        return Path(str(new_value))
    if isinstance(current_val, bool):
        return str(new_value).strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current_val, int):
        return int(new_value)
    if isinstance(current_val, list) or is_list_field:
        return (
            [v.strip() for v in str(new_value).split(",") if v.strip()]
            if isinstance(new_value, str)
            else new_value
        )
    return new_value


def dotted_set(settings: Settings, key: str, value: str) -> None:
    """Set a config value by dotted key. Secret keys go to the OS keyring."""
    if key in _SECRET_FIELDS:
        _keyring_set(_KEYRING_KEYS[key], value)
        return
    normalized_key = "telemetry." + key[5:] if key.startswith("otel.") else key
    parts = normalized_key.split(".", 1)
    if len(parts) == 1:
        target = getattr(settings, parts[0], None)
        if isinstance(target, BaseModel):
            raise ConfigurationError(
                f"Cannot set top-level section '{parts[0]}' directly to a string. "
                f"Use dotted key (e.g. '{parts[0]}.<field>').",
                key=parts[0],
            )
        setattr(settings, parts[0], value)
        return
    section = getattr(settings, parts[0])
    field_name = parts[1]
    current = getattr(section, field_name, None)
    is_list = field_name.endswith("s")
    coerced = _coerce_setting_value(current, value, is_list)
    setattr(section, field_name, coerced)
