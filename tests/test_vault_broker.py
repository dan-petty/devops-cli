"""Unit tests for the enterprise Vault and cloud KMS secret broker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.vault import app as vault_app
from devops_cli.security.vault_broker import (
    VaultSecretBroker,
    parse_vault_uri,
)

runner = CliRunner()


def test_parse_vault_uri() -> None:
    """Test parsing vault:// URIs into path and key components."""
    path, key = parse_vault_uri("vault://secret/data/devops/creds#github_token")
    assert path == "secret/data/devops/creds"
    assert key == "github_token"

    # Path without fragment key
    path_no_key, key_none = parse_vault_uri("vault://secret/data/ci/database")
    assert path_no_key == "secret/data/ci/database"
    assert key_none is None

    # Plain path without vault:// scheme
    plain_path, plain_key = parse_vault_uri("secret/data/plain")
    assert plain_path == "secret/data/plain"
    assert plain_key is None


def test_vault_broker_get_secret_api_success() -> None:
    """Test retrieving a secret from Vault KV-v2 engine successfully."""
    broker = VaultSecretBroker(vault_addr="http://127.0.0.1:8200", vault_token="s.test-token")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "data": {
                "api_key": "vault-secret-value-xyz",
                "username": "admin",
            }
        }
    }

    with patch("devops_cli.http.broker.HttpClientBroker.request", return_value=mock_resp):
        val = broker.get_secret("secret/data/myapp", key="api_key")
        assert val == "vault-secret-value-xyz"

        all_data = broker.get_secret("secret/data/myapp")
        assert isinstance(all_data, dict)
        assert all_data["username"] == "admin"


def test_vault_broker_fallback_to_keyring() -> None:
    """Test seamless fallback to OS Keyring when Vault is unreachable or unconfigured."""
    broker = VaultSecretBroker(vault_addr="http://127.0.0.1:8200", vault_token=None)

    with patch(
        "devops_cli.security.vault_broker.get_keyring_secret", return_value="keyring-cached-token"
    ):
        val = broker.get_secret("secret/data/myapp", key="github.token")
        assert val == "keyring-cached-token"


def test_vault_broker_set_secret_success() -> None:
    """Test writing secret payload to Vault KV-v2 engine."""
    broker = VaultSecretBroker(vault_addr="http://127.0.0.1:8200", vault_token="s.test-token")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"version": 2}}

    with patch("devops_cli.http.broker.HttpClientBroker.request", return_value=mock_resp):
        ok = broker.set_secret("secret/data/myapp", {"token": "new-secret"})
        assert ok is True


def test_vault_broker_get_status() -> None:
    """Test querying Vault health status endpoint."""
    broker = VaultSecretBroker(vault_addr="http://127.0.0.1:8200", vault_token="s.test-token")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "initialized": True,
        "sealed": False,
        "version": "1.15.0",
        "cluster_name": "vault-cluster-local",
    }

    with patch("devops_cli.http.broker.HttpClientBroker.request", return_value=mock_resp):
        status = broker.get_status()
        assert status.initialized is True
        assert status.sealed is False
        assert status.version == "1.15.0"
        assert status.is_healthy is True


def test_cli_vault_status_dry_run() -> None:
    """Test devops vault status CLI subcommand with dry-run."""
    res = runner.invoke(vault_app, ["status", "--dry-run"])
    assert res.exit_code == 0
    assert "vault_health_status" in res.output


def test_cli_vault_get_dry_run() -> None:
    """Test devops vault get CLI subcommand with dry-run."""
    res = runner.invoke(vault_app, ["get", "secret/data/app", "--key", "token", "--dry-run"])
    assert res.exit_code == 0
    assert "secret/data/app" in res.output
    assert "token" in res.output


def test_vault_broker_namespace_and_sync() -> None:
    """Test vault namespace header and sync_to_keyring functionality."""
    broker = VaultSecretBroker(
        vault_addr="http://127.0.0.1:8200",
        vault_token="s.token",
        vault_namespace="admin/ns",
    )
    headers = broker._get_headers()
    assert headers["X-Vault-Namespace"] == "admin/ns"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"data": {"api_key": "val1", "db_pass": "val2"}}}

    with (
        patch("devops_cli.http.broker.HttpClientBroker.request", return_value=mock_resp),
        patch("devops_cli.security.vault_broker.set_keyring_secret", return_value=True),
    ):
        synced = broker.sync_to_keyring("secret/data/app")
        assert synced == 2


def test_vault_broker_error_branches() -> None:
    """Test error handling in get_secret, set_secret, and get_status."""
    broker = VaultSecretBroker(vault_addr="http://127.0.0.1:8200", vault_token="s.token")

    with patch(
        "devops_cli.http.broker.HttpClientBroker.request",
        side_effect=Exception("Connection refused"),
    ):
        # get_secret falls back to keyring
        with patch(
            "devops_cli.security.vault_broker.get_keyring_secret", return_value="fallback-keyring"
        ):
            assert broker.get_secret("secret/data/app", key="token") == "fallback-keyring"

        # set_secret returns False on exception
        assert broker.set_secret("secret/data/app", {"k": "v"}) is False

        # get_status returns sealed status with error message
        status = broker.get_status()
        assert status.sealed is True
        assert "Connection refused" in (status.error_message or "")


def test_vault_broker_validates_address_scheme() -> None:
    with pytest.raises(ValueError, match="scheme"):
        VaultSecretBroker(vault_addr="ftp://vault.example.com:8200")

    with pytest.raises(ValueError, match="traversal|format|invalid"):
        VaultSecretBroker(vault_addr="http://vault.example.com/../traversal")
