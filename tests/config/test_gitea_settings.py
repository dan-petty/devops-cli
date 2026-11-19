"""Tests for Gitea settings and credentials validation (#1090)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from devops_cli.config.env import credential, secret_keys
from devops_cli.config.settings import GiteaConfig, get_gitea_token, load_settings
from tests.support.fakes.keyring import FakeKeyring


def test_gitea_settings_defaults() -> None:
    """Gitea settings default values."""
    config = GiteaConfig()
    assert config.url is None
    assert config.username is None
    assert config.github_branches == ["main"]
    assert config.extra_checkouts == []


def test_gitea_url_accepts_valid_https() -> None:
    """Gitea URL accepts https scheme with no path."""
    config = GiteaConfig(url="https://git.example.com")
    assert config.url == "https://git.example.com"

    config_slash = GiteaConfig(url="https://git.example.com/")
    assert config_slash.url == "https://git.example.com"


def test_gitea_url_refuses_http() -> None:
    """Gitea URL refuses http scheme."""
    with pytest.raises(ValidationError) as exc:
        GiteaConfig(url="http://git.example.com")
    assert "https" in str(exc.value).lower()


def test_gitea_url_refuses_path() -> None:
    """Gitea URL refuses a URL that includes a path."""
    with pytest.raises(ValidationError) as exc:
        GiteaConfig(url="https://git.example.com/api/v1")
    assert "path" in str(exc.value).lower()


def test_gitea_token_credential_declaration() -> None:
    """gitea.token is declared as a managed credential."""
    cred = credential("gitea.token")
    assert cred.key == "gitea.token"
    assert cred.keyring_name == "gitea_token"
    assert "DEVOPS_CLI_GITEA_TOKEN" in cred.env_vars
    assert "gitea.token" in secret_keys()


def test_gitea_token_resolution(
    monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    """gitea.token resolves from environment variable or keyring."""
    monkeypatch.setenv("DEVOPS_CLI_GITEA_TOKEN", "test-token-123")
    settings = load_settings()
    assert get_gitea_token(settings) == "test-token-123"

    # Also test resolution directly from keyring
    monkeypatch.delenv("DEVOPS_CLI_GITEA_TOKEN", raising=False)
    keyring_store.set_password("devops-cli", "gitea_token", "keyring-token-456")
    assert get_gitea_token(load_settings()) == "keyring-token-456"
