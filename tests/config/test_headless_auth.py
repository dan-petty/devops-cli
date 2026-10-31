"""Tests for headless keyring auth fallback."""

from __future__ import annotations

import pytest

from devops_cli.config.os_keyring import (
    get_keyring_secret,
    has_keyring_secret,
    remember_secret,
    store_keyring_secret,
)
from tests.support.fakes.keyring import FakeKeyring


def test_headless_auth_keeps_a_stored_secret_in_memory_only(
    keyring_store: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_HEADLESS_AUTH", "true")

    store_keyring_secret("grafana_token", "FAKE-test-token-123")

    assert (get_keyring_secret("grafana_token"), keyring_store.writes) == (
        "FAKE-test-token-123",
        {},
    )


def test_a_remembered_secret_is_read_before_the_keyring(keyring_store: FakeKeyring) -> None:
    keyring_store.values["ai_api_key"] = "sk-in-keyring"

    remember_secret("ai_api_key", "sk-test-secret")

    assert (
        get_keyring_secret("ai_api_key"),
        has_keyring_secret("ai_api_key"),
        keyring_store.reads,
    ) == ("sk-test-secret", True, [])
