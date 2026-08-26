"""Configuration settings resolution, Pydantic models, and keyring helpers."""

from __future__ import annotations

import operator
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from devops_cli.config import options as opt
from devops_cli.config.constants import (
    CONST_CONFIG_DIR as CONFIG_DIR,
)
from devops_cli.config.constants import (
    CONST_CONFIG_PATH as CONFIG_PATH,
)
from devops_cli.config.constants import (
    CONST_KEYRING_SERVICE as KEYRING_SERVICE,
)
from devops_cli.config.constants import (
    CONST_LLM_CACHE_DATA_DIR,
)
from devops_cli.config.constants import (
    CONST_PROJECT_CONFIG_ENV as PROJECT_CONFIG_ENV,
)
from devops_cli.config.constants import (
    CONST_PROJECT_CONFIG_FILENAME as PROJECT_CONFIG_FILENAME,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_MAX_RETRIES,
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROVIDER,
    DEFAULT_JAEGER_URL,
    DEFAULT_LLM_CACHE_ENABLED,
    DEFAULT_LLM_CACHE_MAX_ENTRIES,
    DEFAULT_LLM_CACHE_TTL_SECONDS,
    DEFAULT_OLLAMA_MAX_PARALLEL,
    DEFAULT_OLLAMA_URLS,
    DEFAULT_OTEL_ENDPOINT,
    DEFAULT_QDRANT_URL,
    DEFAULT_RAG_CHUNK_OVERLAP,
    DEFAULT_RAG_CHUNK_SIZE,
    DEFAULT_RAG_EMBEDDING_MODEL,
    DEFAULT_RAG_SCORE_THRESHOLD,
    DEFAULT_RAG_TOP_K,
    DEFAULT_REPOS_BASE_DIR,
    DEFAULT_SSH_KEY_DIR,
    DEFAULT_SSH_ROTATION_DAYS,
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


class JaegerConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    url: str | None = DEFAULT_JAEGER_URL


class TelemetryConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    enabled: bool = True
    endpoint: str = DEFAULT_OTEL_ENDPOINT


class AIRAGConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    enabled: bool = True
    embedding_model: str = DEFAULT_RAG_EMBEDDING_MODEL
    top_k: int = DEFAULT_RAG_TOP_K
    score_threshold: float = DEFAULT_RAG_SCORE_THRESHOLD
    chunk_size: int = DEFAULT_RAG_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_RAG_CHUNK_OVERLAP


class AICacheConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    enabled: bool = DEFAULT_LLM_CACHE_ENABLED
    dir: Path = CONST_LLM_CACHE_DATA_DIR
    ttl_seconds: int = DEFAULT_LLM_CACHE_TTL_SECONDS
    max_entries: int = DEFAULT_LLM_CACHE_MAX_ENTRIES


class AITaskOverride(BaseModel):
    """Per-task model/server override; unset fields fall back to the parent AIConfig."""

    model_config = ConfigDict(frozen=False)
    provider: str | None = None
    model: str | None = None
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


class AIConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    provider: str = DEFAULT_AI_PROVIDER  # ollama | claude | copilot | openai
    model: str = DEFAULT_AI_MODEL
    ollama_urls: list[str] = Field(default_factory=lambda: list(DEFAULT_OLLAMA_URLS))
    ollama_max_parallel: int = DEFAULT_OLLAMA_MAX_PARALLEL
    api_base_url: str | None = None
    allow_private_network: bool = False
    max_retries: int = DEFAULT_AI_MAX_RETRIES
    tasks: AITasksConfig = AITasksConfig()
    rag: AIRAGConfig = AIRAGConfig()
    cache: AICacheConfig = AICacheConfig()

    @property
    def get_ollama_urls(self) -> list[str]:
        """Return non-empty list of Ollama base URLs."""
        if self.ollama_urls:
            cleaned = [u.strip().rstrip("/") for u in self.ollama_urls if u and u.strip()]
            if cleaned:
                return cleaned
        return list(DEFAULT_OLLAMA_URLS)

    def for_task(self, task: str) -> AIConfig:
        """Return a copy with task-specific overrides from ai.tasks.<task> applied."""
        override: AITaskOverride = getattr(self.tasks, task, AITaskOverride())
        updates = {
            k: v
            for k, v in {
                "provider": override.provider,
                "model": override.model,
                "ollama_urls": override.ollama_urls,
                "ollama_max_parallel": override.ollama_max_parallel,
                "api_base_url": override.api_base_url,
                "max_retries": override.max_retries,
            }.items()
            if v is not None
        }
        return self.model_copy(update=updates) if updates else self


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
    jaeger: JaegerConfig = JaegerConfig()
    telemetry: TelemetryConfig = TelemetryConfig()
    ai: AIConfig = AIConfig()


# TODO (v0.1.1 Feature): MemoryKeyringStore for headless CI environments lacking DBus/SecretService
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


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Merge override into base in-place; override wins on conflict, None skipped."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        elif value is not None:
            base[key] = value


def load_settings() -> Settings:
    """Load settings: global config → project config → env vars (each layer wins)."""
    raw: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}

    # DEVOPS_CLI_CONFIG env var (absolute path) takes precedence over CWD lookup.
    env_config = os.environ.get(PROJECT_CONFIG_ENV)
    project_path = Path(env_config) if env_config else Path(PROJECT_CONFIG_FILENAME)
    if project_path.exists():
        project_raw: dict[str, Any] = yaml.safe_load(project_path.read_text(encoding="utf-8")) or {}
        _deep_merge(raw, project_raw)

    settings = Settings.model_validate(raw)

    # Allow devcontainer and shell environment variables to override file config.
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

    return settings


def get_active_config_path() -> Path:
    """Return active config file path (DEVOPS_CLI_CONFIG > ./config.yaml > ~/.config)."""
    env_config = os.environ.get(PROJECT_CONFIG_ENV)
    project_path = Path(env_config) if env_config else Path(PROJECT_CONFIG_FILENAME)
    if project_path.exists():
        return project_path.resolve()
    return CONFIG_PATH


def save_settings(settings: Settings) -> None:
    """Persist settings to config YAML (secrets stay in keyring only)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = settings.model_dump(mode="json", exclude_none=True)
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    tmp = CONFIG_PATH.with_suffix(".yaml.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, CONFIG_PATH)


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


def get_argocd_token(settings: Settings) -> str | None:
    return _keyring_get(_KEYRING_KEYS[opt.ARGOCD_TOKEN])


def get_ai_api_key(settings: Settings) -> str | None:
    return _keyring_get(_KEYRING_KEYS[opt.AI_API_KEY])


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
    if isinstance(current, Path):
        setattr(section, field_name, Path(value))
    elif isinstance(current, bool):
        setattr(section, field_name, value.strip().lower() in {"1", "true", "yes", "on"})
    elif isinstance(current, int):
        setattr(section, field_name, int(value))
    elif isinstance(current, list) or field_name.endswith("s"):
        if isinstance(value, str):
            setattr(section, field_name, [v.strip() for v in value.split(",") if v.strip()])
        else:
            setattr(section, field_name, value)
    else:
        setattr(section, field_name, value)
