"""Configuration management for devops-cli."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from devops_cli import config_options as opt
from devops_cli.defaults import (
    CONFIG_DIR,
    CONFIG_PATH,
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROVIDER,
    DEFAULT_OLLAMA_URL,
    DEFAULT_REPOS_BASE_DIR,
    DEFAULT_SSH_KEY_DIR,
    DEFAULT_SSH_ROTATION_DAYS,
    DEFAULT_WORKSPACE_FILE,
    KEYRING_SERVICE,
)
from devops_cli.env_vars import OPTION_TO_ENV_VAR

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


class AIConfig(BaseModel):
    model_config = ConfigDict(frozen=False)
    provider: str = DEFAULT_AI_PROVIDER  # ollama | claude | copilot | openai
    model: str = DEFAULT_AI_MODEL
    ollama_url: str = DEFAULT_OLLAMA_URL
    api_base_url: str | None = None


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


def load_settings() -> Settings:
    """Load settings from the config YAML file."""
    if CONFIG_PATH.exists():
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        return Settings.model_validate(raw)
    return Settings()


def save_settings(settings: Settings) -> None:
    """Persist settings to config YAML (secrets stay in keyring only)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = settings.model_dump(mode="json", exclude_none=True)
    CONFIG_PATH.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def get_github_token(settings: Settings) -> str | None:  # noqa: ARG001
    return (
        _keyring_get(_KEYRING_KEYS[opt.GITHUB_TOKEN])
        or os.environ.get(OPTION_TO_ENV_VAR[opt.GITHUB_TOKEN])
        or _github_cli_token()
    )


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
    return _keyring_get(_KEYRING_KEYS[opt.GRAFANA_TOKEN]) or os.environ.get(
        OPTION_TO_ENV_VAR[opt.GRAFANA_TOKEN]
    )


def get_argocd_token(settings: Settings) -> str | None:  # noqa: ARG001
    return _keyring_get(_KEYRING_KEYS[opt.ARGOCD_TOKEN]) or os.environ.get(
        OPTION_TO_ENV_VAR[opt.ARGOCD_TOKEN]
    )


def get_ai_api_key(settings: Settings) -> str | None:  # noqa: ARG001
    return _keyring_get(_KEYRING_KEYS[opt.AI_API_KEY]) or os.environ.get(
        OPTION_TO_ENV_VAR[opt.AI_API_KEY]
    )


def dotted_get(settings: Settings, key: str) -> Any:
    """Get a config value by dotted key, e.g. 'github.default_org'."""
    parts = key.split(".", 1)
    if len(parts) == 1:
        return getattr(settings, parts[0])
    return getattr(getattr(settings, parts[0]), parts[1])


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
    else:
        setattr(section, field_name, value)
