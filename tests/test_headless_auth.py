"""Tests for headless keyring auth fallback."""

from __future__ import annotations

import os

from devops_cli.config import options as opt
from devops_cli.config.settings import (
    _EPHEMERAL_CI_SECRETS,
    _keyring_get,
    _keyring_set,
)


def test_ephemeral_keyring_fallback(monkeypatch: os._Environ) -> None:
    _EPHEMERAL_CI_SECRETS.clear()
    monkeypatch.setenv("DEVOPS_CLI_HEADLESS_AUTH", "true")

    _keyring_set("github_token", "ghp_test_token_123")
    assert _keyring_get("github_token") == "ghp_test_token_123"


def test_ephemeral_keyring_options() -> None:
    _EPHEMERAL_CI_SECRETS.clear()
    _EPHEMERAL_CI_SECRETS["ai_api_key"] = "sk-test-secret"
    assert _keyring_get("ai_api_key") == "sk-test-secret"
    assert opt.KEYRING_KEYS[opt.AI_API_KEY] == "ai_api_key"
