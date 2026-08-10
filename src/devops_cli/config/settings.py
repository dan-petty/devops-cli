"""Configuration settings resolution, Pydantic models, and keyring helpers."""

from __future__ import annotations

import operator
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

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
    CONST_PROJECT_CONFIG_ENV as PROJECT_CONFIG_ENV,
)
from devops_cli.config.constants import (
    CONST_PROJECT_CONFIG_FILENAME as PROJECT_CONFIG_FILENAME,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROVIDER,
    DEFAULT_OLLAMA_URL,
    DEFAULT_REPOS_BASE_DIR,
    DEFAULT_SSH_KEY_DIR,
    DEFAULT_SSH_ROTATION_DAYS,
    DEFAULT_WORKSPACE_FILE,
)
from devops_cli.config.env import OPTION_TO_ENV_VAR

_SECRET_FIELDS: frozenset[str] = opt.SECRET_CONFIG_OPTIONS
_KEYRING_KEYS: dict[str, str] = opt.KEYRING_KEYS


class SecretStorageError(RuntimeError):
    """Raised when a secret cannot be stored in the configured keyring backend."""


def _ensure_keyring_backend() -> bool:
    """Ensure keyring has a usable backend, falling back to keyrings.alt when available."""
    import keyring
    from keyring.backends.fail import Keyring as FailKeyring

    if not isinstance(keyring.get_keyring(), FailKeyring):
        return True

    try:
        from keyrings.alt.file import PlaintextKeyring  # type: ignore[import-untyped]

        keyring.set_keyring(PlaintextKeyring())
    except Exception:
        return False

    return not isinstance(keyring.get_keyring(), FailKeyring)


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


class AITaskOverride(BaseModel):
    """Per-task model/server override; unset fields fall back to the parent AIConfig."""

    model_config = ConfigDict(frozen=False)
    provider: str | None = None
    model: str | None = None
    ollama_url: str | None = None
    api_base_url: str | None = None


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
    ollama_url: str = DEFAULT_OLLAMA_URL
    api_base_url: str | None = None
    allow_private_network: bool = False
    tasks: AITasksConfig = AITasksConfig()

    def for_task(self, task: str) -> AIConfig:
        """Return a copy with task-specific overrides from ai.tasks.<task> applied."""
        override: AITaskOverride = getattr(self.tasks, task, AITaskOverride())
        updates = {
            k: v
            for k, v in {
                "provider": override.provider,
                "model": override.model,
                "ollama_url": override.ollama_url,
                "api_base_url": override.api_base_url,
            }.items()
            if v is not None
        }
        return self.model_copy(update=updates) if updates else self


class Settings(BaseModel):
    model_config = ConfigDict(frozen=False)
    github: GitHubConfig = GitHubConfig()
    ssh: SSHConfig = SSHConfig()
    repos: ReposConfig = ReposConfig()
    workspace: WorkspaceConfig = WorkspaceConfig()
    grafana: GrafanaConfig = GrafanaConfig()
    prometheus: PrometheusConfig = PrometheusConfig()
    argocd: ArgoCDConfig = ArgoCDConfig()
    ai: AIConfig = AIConfig()


def _keyring_get(key: str) -> str | None:
    import keyring
    from keyring.errors import NoKeyringError

    if not _ensure_keyring_backend():
        return None

    try:
        return keyring.get_password(KEYRING_SERVICE, key)
    except NoKeyringError:
        return None
    except Exception:
        return None


def _keyring_set(key: str, value: str) -> None:
    import keyring
    from keyring.errors import NoKeyringError

    if not _ensure_keyring_backend():
        raise SecretStorageError(
            "No keyring backend is available in this environment. "
            "Install keyrings.alt or configure an OS keyring backend."
        )

    try:
        keyring.set_password(KEYRING_SERVICE, key, value)
    except NoKeyringError as exc:
        raise SecretStorageError(
            "No keyring backend is available in this environment. "
            "Install keyrings.alt or configure an OS keyring backend."
        ) from exc
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


def save_settings(settings: Settings) -> None:
    """Persist settings to config YAML (secrets stay in keyring only)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = settings.model_dump(mode="json", exclude_none=True)
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    tmp = CONFIG_PATH.with_suffix(".yaml.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, CONFIG_PATH)


def get_github_token(settings: Settings) -> str | None:  # noqa: ARG001
    return _keyring_get(_KEYRING_KEYS[opt.GITHUB_TOKEN]) or _github_cli_token()


def _github_cli_token() -> str | None:
    """Return token from `gh auth token` when GitHub CLI is authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except FileNotFoundError, OSError, subprocess.SubprocessError:
        return None

    if result.returncode != 0:
        return None

    token = result.stdout.strip()
    return token or None


def get_grafana_token(settings: Settings) -> str | None:  # noqa: ARG001
    return _keyring_get(_KEYRING_KEYS[opt.GRAFANA_TOKEN])


def get_argocd_token(settings: Settings) -> str | None:  # noqa: ARG001
    return _keyring_get(_KEYRING_KEYS[opt.ARGOCD_TOKEN])


def get_ai_api_key(settings: Settings) -> str | None:  # noqa: ARG001
    return _keyring_get(_KEYRING_KEYS[opt.AI_API_KEY])


def dotted_get(settings: Settings, key: str) -> Any:
    """Get a config value by dotted key, e.g. 'github.default_org'."""
    return operator.attrgetter(key)(settings)


def dotted_set(settings: Settings, key: str, value: str) -> None:
    """Set a config value by dotted key. Secret keys go to the OS keyring."""
    if key in _SECRET_FIELDS:
        _keyring_set(_KEYRING_KEYS[key], value)
        return
    parts = key.split(".", 1)
    if len(parts) == 1:
        setattr(settings, parts[0], value)
        return
    section = getattr(settings, parts[0])
    field_name = parts[1]
    current = getattr(section, field_name, None)
    if isinstance(current, Path):
        setattr(section, field_name, Path(value))
    elif isinstance(current, int):
        setattr(section, field_name, int(value))
    elif isinstance(current, bool):
        setattr(section, field_name, value.strip().lower() in {"1", "true", "yes", "on"})
    else:
        setattr(section, field_name, value)
