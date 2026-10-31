"""Tests for the dashboard Valkey data provider."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from devops_cli.ui.data_providers import ValkeySummary, fetch_valkey_status
from devops_cli.valkey.client import install_valkey_client, reset_valkey_client
from tests.support.certificates import LocalCa
from tests.support.fakes.valkey import bulk_reply, serving_valkey
from tests.web_fakes import scripted_resolver

pytestmark = pytest.mark.usefixtures("keyring_store")

_VALKEY_INFO_TEXT = (
    "# Server\r\nredis_version:7.2.4\r\nserver_name:valkey\r\nvalkey_version:8.0.0\r\n"
    "uptime_in_seconds:3600\r\n\r\n"
    "# Clients\r\nconnected_clients:4\r\n\r\n"
    "# Memory\r\nused_memory:2516582\r\nused_memory_human:2.40M\r\n\r\n"
    "# Stats\r\ntotal_commands_processed:5000\r\nkeyspace_hits:800\r\nkeyspace_misses:200\r\n"
)


def test_fetch_valkey_status_reads_the_flat_info_the_client_returns(
    config: Callable[..., Path],
) -> None:
    """The panel shows what a server reports: version, uptime, memory, clients, commands, hits."""
    replies = {"INFO": bulk_reply(_VALKEY_INFO_TEXT.encode()), "DBSIZE": b":150\r\n"}
    with serving_valkey(replies) as (port, _received):
        config(valkey={"url": f"valkey://127.0.0.1:{port}"})
        summary = fetch_valkey_status()

    assert summary == ValkeySummary(
        connected=True,
        endpoint=f"127.0.0.1:{port}",
        version="8.0.0",
        uptime_seconds=3600,
        used_memory="2.40M",
        hit_ratio=80.0,
        connected_clients=4,
        total_commands=5000,
        key_count=150,
    )


def test_fetch_valkey_status_connects_over_tls_for_a_valkeys_url(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch, local_ca: LocalCa
) -> None:
    """The panel dials the `valkeys://` URL over TLS and checks the certificate against its host."""
    scripted_resolver(monkeypatch, {"example.com": [["127.0.0.1"]]})
    replies = {"INFO": bulk_reply(_VALKEY_INFO_TEXT.encode()), "DBSIZE": b":150\r\n"}
    tls = local_ca.server_context("example.com")
    with serving_valkey(replies, tls=tls) as (port, _received):
        config(valkey={"url": f"valkeys://example.com:{port}"})
        summary = fetch_valkey_status()

    assert summary == ValkeySummary(
        connected=True,
        endpoint=f"example.com:{port}",
        version="8.0.0",
        uptime_seconds=3600,
        used_memory="2.40M",
        hit_ratio=80.0,
        connected_clients=4,
        total_commands=5000,
        key_count=150,
    )


@pytest.mark.parametrize(
    "plaintext_password",
    [
        pytest.param(None, id="keyring-only"),
        pytest.param("plaintext-password", id="keyring-over-plaintext-setting"),
    ],
)
def test_fetch_valkey_status_authenticates_with_the_keyring_password(
    config: Callable[..., Path], keyring_store: Any, plaintext_password: str | None
) -> None:
    """The panel sends the password `get_valkey_password` resolves, never the plaintext setting."""
    keyring_store.values["valkey_password"] = "keyring-password"
    with serving_valkey({"INFO": bulk_reply(_VALKEY_INFO_TEXT.encode())}) as (port, received):
        config(valkey={"url": f"valkey://127.0.0.1:{port}", "password": plaintext_password})
        fetch_valkey_status()

    assert received[0] == ["AUTH", "keyring-password"]


def test_fetch_valkey_status_failure() -> None:
    """fetch_valkey_status returns offline summary when connection fails."""
    mock_client = MagicMock()
    mock_client.info.side_effect = Exception("Connection refused")
    install_valkey_client(mock_client)
    try:
        summary = fetch_valkey_status()
        assert isinstance(summary, ValkeySummary)
        assert summary.connected is False
        assert summary.version == "Offline"
    finally:
        reset_valkey_client()
