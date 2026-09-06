"""Unit tests for HashiCorp Vault enterprise secret broker CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.vault import _validate_vault_path, app
from devops_cli.security.vault_broker import VaultStatus

runner = CliRunner()


def test_validate_vault_path_valid() -> None:
    _validate_vault_path("secret/data/myapp")
    _validate_vault_path("vault://secret/data/myapp#token")
    _validate_vault_path("secret/my-app_1/api-key")


def test_validate_vault_path_empty_error() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        _validate_vault_path("   ")


def test_validate_vault_path_traversal_error() -> None:
    with pytest.raises(ValueError, match="cannot contain '\\.\\.' traversal"):
        _validate_vault_path("secret/../../etc/passwd")


def test_validate_vault_path_invalid_characters() -> None:
    with pytest.raises(ValueError, match="contains invalid characters"):
        _validate_vault_path("secret/myapp;rm -rf /")


def test_vault_status_healthy() -> None:
    mock_status = VaultStatus(
        initialized=True,
        sealed=False,
        version="1.15.2",
        cluster_name="vault-cluster-main",
        error_message=None,
    )
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        broker = MagicMock()
        broker.vault_addr = "http://vault.example.com:8200"
        broker.get_status.return_value = mock_status
        mock_cls.return_value = broker

        res = runner.invoke(app, ["status", "--addr", "http://vault.example.com:8200"])
        assert res.exit_code == 0
        assert "Vault Address" in res.output
        assert "1.15.2" in res.output
        assert "Healthy" in res.output


def test_vault_status_degraded_with_error() -> None:
    mock_status = VaultStatus(
        initialized=False,
        sealed=True,
        version="",
        cluster_name="",
        error_message="Connection refused to cluster port 8200",
    )
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        broker = MagicMock()
        broker.vault_addr = "http://vault.example.com:8200"
        broker.get_status.return_value = mock_status
        mock_cls.return_value = broker

        res = runner.invoke(app, ["status"])
        assert res.exit_code == 0
        assert "Connection refused" in res.output
        assert "Sealed" in res.output
        assert "Degraded" in res.output


def test_vault_status_dry_run() -> None:
    res = runner.invoke(app, ["status", "--dry-run"])
    assert res.exit_code == 0
    assert "vault_health_status" in res.output or "DRY RUN" in res.output


def test_vault_get_invalid_path() -> None:
    res = runner.invoke(app, ["get", "invalid/../traversal"])
    assert res.exit_code == 1
    assert "traversal" in res.output


def test_vault_get_dry_run() -> None:
    res = runner.invoke(app, ["get", "secret/data/myapp", "--dry-run"])
    assert res.exit_code == 0
    assert "vault_get_secret" in res.output or "DRY RUN" in res.output


def test_vault_get_not_found() -> None:
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        broker = MagicMock()
        broker.vault_addr = "http://vault:8200"
        broker.get_secret.return_value = None
        mock_cls.return_value = broker

        res = runner.invoke(app, ["get", "secret/data/missing"])
        assert res.exit_code == 1
        assert "Secret not found" in res.output


def test_vault_get_dict_masked_and_show() -> None:
    mock_dict = {"api_key": "supersecret123", "db_password": "mypassword"}
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        broker = MagicMock()
        broker.vault_addr = "http://vault:8200"
        broker.get_secret.return_value = mock_dict
        mock_cls.return_value = broker

        # Masked
        res = runner.invoke(app, ["get", "secret/data/myapp"])
        assert res.exit_code == 0
        assert "***REDACTED***" in res.output
        assert "supersecret123" not in res.output

        # Shown
        res_show = runner.invoke(app, ["get", "secret/data/myapp", "--show"])
        assert res_show.exit_code == 0
        assert "supersecret123" in res_show.output


def test_vault_get_scalar_masked_and_show() -> None:
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        broker = MagicMock()
        broker.vault_addr = "http://vault:8200"
        broker.get_secret.return_value = "token_value_xyz"
        mock_cls.return_value = broker

        # Masked
        res = runner.invoke(app, ["get", "secret/data/myapp", "--key", "token"])
        assert res.exit_code == 0
        assert "***REDACTED***" in res.output

        # Shown
        res_show = runner.invoke(app, ["get", "secret/data/myapp", "--key", "token", "--show"])
        assert res_show.exit_code == 0
        assert "token_value_xyz" in res_show.output


def test_vault_set_invalid_path() -> None:
    res = runner.invoke(app, ["set", "path/../bad", "KEY=VAL"])
    assert res.exit_code == 1
    assert "traversal" in res.output


def test_vault_set_no_valid_pairs() -> None:
    res = runner.invoke(app, ["set", "secret/data/myapp", "invalid_no_equal_sign"])
    assert res.exit_code == 1
    assert "No valid KEY=VALUE pairs" in res.output


def test_vault_set_dry_run() -> None:
    res = runner.invoke(app, ["set", "secret/data/myapp", "FOO=BAR", "--dry-run"])
    assert res.exit_code == 0
    assert "vault_set_secret" in res.output or "DRY RUN" in res.output


def test_vault_set_success() -> None:
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        broker = MagicMock()
        broker.vault_addr = "http://vault:8200"
        broker.set_secret.return_value = True
        mock_cls.return_value = broker

        res = runner.invoke(app, ["set", "secret/data/myapp", "KEY1=VAL1", "KEY2=VAL2"])
        assert res.exit_code == 0
        assert "Successfully stored 2 secret(s)" in res.output


def test_vault_set_failure() -> None:
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        broker = MagicMock()
        broker.vault_addr = "http://vault:8200"
        broker.set_secret.return_value = False
        mock_cls.return_value = broker

        res = runner.invoke(app, ["set", "secret/data/myapp", "KEY=VAL"])
        assert res.exit_code == 1
        assert "Failed to write secrets" in res.output


def test_vault_sync_invalid_path() -> None:
    res = runner.invoke(app, ["sync", "path/../bad"])
    assert res.exit_code == 1
    assert "traversal" in res.output


def test_vault_sync_dry_run() -> None:
    res = runner.invoke(app, ["sync", "secret/data/myapp", "-k", "token", "--dry-run"])
    assert res.exit_code == 0
    assert "vault_sync_keyring" in res.output or "DRY RUN" in res.output


def test_vault_sync_success() -> None:
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        broker = MagicMock()
        broker.vault_addr = "http://vault:8200"
        broker.sync_to_keyring.return_value = 3
        mock_cls.return_value = broker

        res = runner.invoke(app, ["sync", "secret/data/myapp", "--key", "k1", "--key", "k2"])
        assert res.exit_code == 0
        assert "Synchronized 3 secret(s)" in res.output
        broker.sync_to_keyring.assert_called_once_with("secret/data/myapp", keys=["k1", "k2"])
