"""Tests for GitHub Actions libsodium-sealed repository secrets synchronization."""

from __future__ import annotations

from base64 import b64decode
from unittest.mock import MagicMock, patch

import pytest
from nacl import encoding, public
from typer.testing import CliRunner

from devops_cli.commands.gh import app
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.secrets import (
    GitHubPublicKey,
    SecretSyncItem,
    SecretSyncResult,
    _resolve_secret_from_source,
    _upload_encrypted_secret,
    encrypt_secret,
    get_repository_public_key,
    list_repository_secrets,
    sync_repository_secrets,
)

runner = CliRunner()


@pytest.fixture
def mock_keypair() -> tuple[str, public.PrivateKey]:
    """Generate ephemeral keypair and return base64-encoded public key and private key object."""
    sk = public.PrivateKey.generate()
    pk = sk.public_key
    pk_b64 = pk.encode(encoder=encoding.Base64Encoder).decode("utf-8")
    return pk_b64, sk


def test_encrypt_secret_roundtrip(mock_keypair: tuple[str, public.PrivateKey]) -> None:
    pk_b64, sk = mock_keypair
    secret_text = "super-secret-token-12345"
    encrypted_b64 = encrypt_secret(pk_b64, secret_text)
    assert encrypted_b64 != secret_text

    # Decrypt with private key
    encrypted_bytes = b64decode(encrypted_b64.encode("utf-8"))
    sealed_box = public.SealedBox(sk)
    decrypted = sealed_box.decrypt(encrypted_bytes).decode("utf-8")
    assert decrypted == secret_text


def test_encrypt_secret_invalid_key() -> None:
    with pytest.raises(GitHubOperationError) as exc_info:
        encrypt_secret("invalid-base64-key!@#", "mysecret")
    assert "Failed to encrypt secret" in str(exc_info.value)


@patch("devops_cli.github.secrets.run_subprocess")
def test_get_repository_public_key_success(mock_sub: MagicMock) -> None:
    mock_sub.return_value = MagicMock(
        returncode=0,
        stdout='{"key_id": "key-123", "key": "dGVzdC1wdWJsaWMta2V5"}',
    )
    pk = get_repository_public_key("dan-petty/devops-cli")
    assert pk.key_id == "key-123"
    assert pk.key == "dGVzdC1wdWJsaWMta2V5"


@patch("devops_cli.github.secrets.run_subprocess")
def test_get_repository_public_key_failure(mock_sub: MagicMock) -> None:
    mock_sub.return_value = MagicMock(returncode=1, stdout="", stderr="HTTP 403 Forbidden")
    with pytest.raises(GitHubOperationError) as exc_info:
        get_repository_public_key("dan-petty/devops-cli")
    assert "Failed to get Actions public key" in str(exc_info.value)


@patch("devops_cli.github.secrets.run_subprocess")
def test_get_repository_public_key_invalid_json(mock_sub: MagicMock) -> None:
    mock_sub.return_value = MagicMock(returncode=0, stdout="not valid json")
    with pytest.raises(GitHubOperationError) as exc_info:
        get_repository_public_key("dan-petty/devops-cli")
    assert "Invalid public key response" in str(exc_info.value)


@patch("devops_cli.github.secrets.run_subprocess")
def test_list_repository_secrets_success(mock_sub: MagicMock) -> None:
    mock_sub.return_value = MagicMock(
        returncode=0,
        stdout='{"secrets": [{"name": "MY_SECRET_1"}, {"name": "MY_SECRET_2"}]}',
    )
    secrets = list_repository_secrets("dan-petty/devops-cli")
    assert secrets == ["MY_SECRET_1", "MY_SECRET_2"]


@patch("devops_cli.github.secrets.run_subprocess")
def test_list_repository_secrets_empty_on_error(mock_sub: MagicMock) -> None:
    mock_sub.return_value = MagicMock(returncode=1, stdout="", stderr="error")
    secrets = list_repository_secrets("dan-petty/devops-cli")
    assert secrets == []


@patch("devops_cli.github.secrets.get_keyring_secret")
def test_resolve_secret_keyring(mock_keyring: MagicMock) -> None:
    mock_keyring.return_value = "keyring-val"
    res = _resolve_secret_from_source("api_key", source="keyring")
    assert res == "keyring-val"


@patch("devops_cli.security.vault_broker.VaultSecretBroker")
def test_resolve_secret_vault(mock_broker_cls: MagicMock) -> None:
    mock_broker = MagicMock()
    mock_broker.get_secret.return_value = "vault-val"
    mock_broker_cls.return_value = mock_broker
    res = _resolve_secret_from_source("api_key", source="vault", vault_path="secret/my-app")
    assert res == "vault-val"
    mock_broker.get_secret.assert_called_once_with("secret/my-app", key="api_key")


def test_resolve_secret_unsupported_source() -> None:
    with pytest.raises(GitHubOperationError) as exc_info:
        _resolve_secret_from_source("test", source="unsupported_store")
    assert "Unsupported secret source" in str(exc_info.value)


@patch("devops_cli.github.secrets.run_subprocess")
def test_upload_encrypted_secret_success(mock_sub: MagicMock) -> None:
    mock_sub.return_value = MagicMock(returncode=0, stdout="")
    success = _upload_encrypted_secret("dan-petty/devops-cli", "TEST_KEY", "enc-value", "key-id")
    assert success is True


@patch("devops_cli.github.secrets.run_subprocess")
def test_upload_encrypted_secret_failure(mock_sub: MagicMock) -> None:
    mock_sub.return_value = MagicMock(returncode=1, stdout="", stderr="Upload rejected")
    success = _upload_encrypted_secret("dan-petty/devops-cli", "TEST_KEY", "enc-value", "key-id")
    assert success is False


def test_sync_repository_secrets_empty_list() -> None:
    res = sync_repository_secrets("dan-petty/devops-cli", secret_names=[])
    assert len(res.synced_secrets) == 0
    assert len(res.missing_secrets) == 0


@patch("devops_cli.github.secrets._resolve_secret_from_source")
def test_sync_repository_secrets_missing_secret(mock_resolve: MagicMock) -> None:
    mock_resolve.return_value = None
    res = sync_repository_secrets("dan-petty/devops-cli", secret_names=["NONEXISTENT"])
    assert "NONEXISTENT" in res.missing_secrets
    assert len(res.items) == 1
    assert res.items[0].status == "missing"


@patch("devops_cli.github.secrets._resolve_secret_from_source")
def test_sync_repository_secrets_dry_run(mock_resolve: MagicMock) -> None:
    mock_resolve.return_value = "dummy-secret-value"
    res = sync_repository_secrets("dan-petty/devops-cli", secret_names=["MY_SECRET"], dry_run=True)
    assert res.dry_run is True
    assert "MY_SECRET" in res.synced_secrets
    assert res.items[0].status == "synced"
    assert "dry-run" in res.items[0].message


@patch("devops_cli.github.secrets._upload_encrypted_secret")
@patch("devops_cli.github.secrets.get_repository_public_key")
@patch("devops_cli.github.secrets._resolve_secret_from_source")
def test_sync_repository_secrets_live_success(
    mock_resolve: MagicMock,
    mock_pk: MagicMock,
    mock_upload: MagicMock,
    mock_keypair: tuple[str, public.PrivateKey],
) -> None:
    pk_b64, _ = mock_keypair
    mock_resolve.return_value = "live-secret-val"
    mock_pk.return_value = GitHubPublicKey(key_id="pk-1", key=pk_b64)
    mock_upload.return_value = True

    res = sync_repository_secrets("dan-petty/devops-cli", secret_names=["SECRET_A"], dry_run=False)
    assert "SECRET_A" in res.synced_secrets
    assert len(res.failed_secrets) == 0
    assert mock_upload.call_count == 1


@patch("devops_cli.github.secrets._upload_encrypted_secret")
@patch("devops_cli.github.secrets.get_repository_public_key")
@patch("devops_cli.github.secrets._resolve_secret_from_source")
def test_sync_repository_secrets_upload_failure(
    mock_resolve: MagicMock,
    mock_pk: MagicMock,
    mock_upload: MagicMock,
    mock_keypair: tuple[str, public.PrivateKey],
) -> None:
    pk_b64, _ = mock_keypair
    mock_resolve.return_value = "live-secret-val"
    mock_pk.return_value = GitHubPublicKey(key_id="pk-1", key=pk_b64)
    mock_upload.return_value = False

    res = sync_repository_secrets("dan-petty/devops-cli", secret_names=["SECRET_A"], dry_run=False)
    assert "SECRET_A" in res.failed_secrets
    assert len(res.synced_secrets) == 0


@patch("devops_cli.commands.gh.list_repository_secrets")
def test_cli_secrets_list(mock_list: MagicMock) -> None:
    mock_list.return_value = ["GITHUB_TOKEN", "DOCKER_PASSWORD"]
    res = runner.invoke(app, ["secrets", "list", "--repo", "dan-petty/devops-cli"])
    assert res.exit_code == 0
    assert "GITHUB_TOKEN" in res.stdout
    assert "DOCKER_PASSWORD" in res.stdout


@patch("devops_cli.commands.gh.list_repository_secrets")
def test_cli_secrets_list_empty(mock_list: MagicMock) -> None:
    mock_list.return_value = []
    res = runner.invoke(app, ["secrets", "list", "--repo", "dan-petty/devops-cli"])
    assert res.exit_code == 0
    assert "No repository secrets found" in res.stdout


@patch("devops_cli.commands.gh.sync_repository_secrets")
def test_cli_secrets_sync_dry_run(mock_sync: MagicMock) -> None:
    mock_sync.return_value = SecretSyncResult(
        synced_secrets=["MY_TOKEN"],
        items=[
            SecretSyncItem(name="MY_TOKEN", source="keyring", status="synced", message="dry-run")
        ],
        dry_run=True,
    )
    res = runner.invoke(
        app,
        ["secrets", "sync", "-n", "MY_TOKEN", "--repo", "dan-petty/devops-cli", "--dry-run"],
    )
    assert res.exit_code == 0
    assert "DRY RUN" in res.stdout
    assert "Synced: 1" in res.stdout


@patch("devops_cli.commands.gh.sync_repository_secrets")
def test_cli_secrets_sync_failure_exit(mock_sync: MagicMock) -> None:
    mock_sync.return_value = SecretSyncResult(
        failed_secrets=["FAIL_TOKEN"],
        items=[
            SecretSyncItem(name="FAIL_TOKEN", source="keyring", status="failed", message="Rejected")
        ],
        dry_run=False,
    )
    res = runner.invoke(
        app,
        ["secrets", "sync", "-n", "FAIL_TOKEN", "--repo", "dan-petty/devops-cli"],
    )
    assert res.exit_code == 1
    assert "Failed: 1" in res.stdout
