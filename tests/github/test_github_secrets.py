"""Tests for GitHub Actions libsodium-sealed repository secrets synchronization."""

from __future__ import annotations

import json
import time
from base64 import b64decode
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

import httpx2
import pytest
from nacl import encoding, public

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.exceptions.vault import VaultAuthenticationError
from devops_cli.github.secrets import (
    encrypt_secret,
    get_repository_public_key,
    list_repository_secrets,
    sync_repository_secrets,
)
from tests.support.fakes.process import ProcessAnswer

if TYPE_CHECKING:
    from tests.support.fakes.keyring import KeyringFake
    from tests.support.fakes.process import ProcessFake

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture(autouse=True)
def _answer_rate_limit(process_fake: ProcessFake) -> None:
    payload = json.dumps(
        {
            "resources": {
                name: {
                    "limit": 5000,
                    "used": 10,
                    "remaining": 4990,
                    "reset": int(time.time()) + 600,
                }
                for name in ("core", "graphql", "search")
            }
        }
    )
    process_fake.answer(["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=payload))


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

    encrypted_bytes = b64decode(encrypted_b64.encode("utf-8"))
    sealed_box = public.SealedBox(sk)
    decrypted = sealed_box.decrypt(encrypted_bytes).decode("utf-8")
    assert decrypted == secret_text


def test_encrypt_secret_invalid_key() -> None:
    with pytest.raises(GitHubOperationError) as exc_info:
        encrypt_secret("invalid-base64-key!@#", "mysecret")
    assert "Failed to encrypt secret" in str(exc_info.value)


def test_get_repository_public_key_parses_json_payload(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/actions/secrets/public-key"],
        ProcessAnswer(stdout='{"key_id": "key-123", "key": "dGVzdC1wdWJsaWMta2V5"}'),
    )
    pk = get_repository_public_key("dan-petty/devops-cli")
    assert pk.key_id == "key-123"
    assert pk.key == "dGVzdC1wdWJsaWMta2V5"


def test_get_repository_public_key_raises_on_gh_error(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/actions/secrets/public-key"],
        ProcessAnswer(returncode=1, stderr="HTTP 403 Forbidden"),
    )
    with pytest.raises(GitHubOperationError) as exc_info:
        get_repository_public_key("dan-petty/devops-cli")
    assert "Failed to get Actions public key" in str(exc_info.value)


def test_get_repository_public_key_raises_on_invalid_json(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/actions/secrets/public-key"],
        ProcessAnswer(stdout="not valid json"),
    )
    with pytest.raises(GitHubOperationError) as exc_info:
        get_repository_public_key("dan-petty/devops-cli")
    assert "Invalid public key response" in str(exc_info.value)


def test_list_repository_secrets_returns_configured_names(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/actions/secrets"],
        ProcessAnswer(stdout='{"secrets": [{"name": "MY_SECRET_1"}, {"name": "MY_SECRET_2"}]}'),
    )
    secrets = list_repository_secrets("dan-petty/devops-cli")
    assert secrets == ["MY_SECRET_1", "MY_SECRET_2"]


def test_list_repository_secrets_returns_empty_list_on_gh_error(
    process_fake: ProcessFake,
) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/actions/secrets"],
        ProcessAnswer(returncode=1, stderr="error"),
    )
    secrets = list_repository_secrets("dan-petty/devops-cli")
    assert secrets == []


def test_resolve_secret_keyring_retrieves_stored_entry(keyring_store: KeyringFake) -> None:
    keyring_store.set_password("devops-cli", "api_key", "keyring-val")
    result = sync_repository_secrets(
        "dan-petty/devops-cli", secret_names=["api_key"], source="keyring", dry_run=True
    )
    assert result.synced_secrets == ["api_key"]


class VaultApiFake:
    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], tuple[int, Any]] = {}
        self.requested: list[str] = []

    def respond(self, method: str, url: str, status_code: int = 200, json_data: Any = None) -> None:
        self.routes[(method.upper(), url)] = (status_code, json_data)

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requested.append(str(request.url))
        key = (request.method.upper(), str(request.url))
        if key in self.routes:
            status_code, json_data = self.routes[key]
            content = json.dumps(json_data).encode("utf-8") if json_data is not None else b""
            return httpx2.Response(
                status_code=status_code,
                content=content,
                request=request,
                headers={"content-type": "application/json"},
            )
        return httpx2.Response(status_code=404, content=b"{}", request=request)


@pytest.fixture
def vault_api() -> Iterator[VaultApiFake]:
    from devops_cli.http.broker import get_broker, reset_broker
    from devops_cli.http.egress import EgressLevel

    api = VaultApiFake()
    transport = httpx2.MockTransport(api.handle)
    broker = get_broker()
    client = httpx2.Client(transport=transport)
    broker._sync_clients[EgressLevel.PRIVATE] = client
    try:
        yield api
    finally:
        reset_broker()


def test_resolve_secret_vault_reads_path_through_http(vault_api: VaultApiFake) -> None:
    vault_api.respond(
        "GET",
        "http://127.0.0.1:8200/v1/secret/my-app",
        200,
        {"data": {"data": {"api_key": "vault-val"}}},
    )
    result = sync_repository_secrets(
        "dan-petty/devops-cli",
        secret_names=["api_key"],
        source="vault",
        vault_path="secret/my-app",
        dry_run=True,
    )
    assert result.synced_secrets == ["api_key"]


@pytest.fixture
def vault_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give the Vault broker a token from the environment, and nothing else from the shell."""
    from devops_cli.security.secrets import reset_resolver

    for name in ("VAULT_NAMESPACE", "DEVOPS_CLI_VAULT_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:8200")
    monkeypatch.setenv("VAULT_TOKEN", "s.env-token")
    reset_resolver()


@pytest.mark.usefixtures("vault_token")
def test_vault_source_with_a_rejected_token_uploads_nothing(
    vault_api: VaultApiFake, cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """A 403 from Vault fails the sync through the command's handler; nothing reaches GitHub."""
    vault_api.respond("GET", "http://127.0.0.1:8200/v1/secret/devops", 403, {})
    res = cli(
        "gh", "secrets", "sync", "-n", "A,B", "--repo", "dan-petty/devops-cli", "--source", "vault"
    )
    assert res.exit_code == 1
    assert "Vault rejected the token from the environment (HTTP 403)" in res.output
    assert not any(
        call.argv[:2] == ("gh", "api") and "secrets" in call.argv for call in process_fake.calls
    )


@pytest.mark.usefixtures("vault_token")
def test_vault_source_reports_an_absent_key_missing_without_reading_the_keyring(
    vault_api: VaultApiFake, keyring_store: KeyringFake
) -> None:
    """A field Vault lacks is missing; the keyring entry of that name is never uploaded."""
    keyring_store.set_password("devops-cli", "ABSENT", "keyring-leak")
    vault_api.respond(
        "GET",
        "http://127.0.0.1:8200/v1/secret/devops",
        200,
        {"data": {"data": {"OTHER": "x"}}},
    )
    result = sync_repository_secrets(
        "dan-petty/devops-cli", secret_names=["ABSENT"], source="vault"
    )
    assert (result.missing_secrets, result.synced_secrets) == (["ABSENT"], [])


@pytest.mark.usefixtures("vault_token")
def test_vault_source_dry_run_sends_no_request(vault_api: VaultApiFake) -> None:
    """A dry run names what it would read from Vault and asks Vault nothing."""
    result = sync_repository_secrets(
        "dan-petty/devops-cli", secret_names=["A"], source="vault", dry_run=True
    )
    assert (result.synced_secrets, "Would read from Vault" in result.items[0].message) == (
        ["A"],
        True,
    )
    assert not vault_api.requested


def test_vault_source_without_a_token_raises_before_any_request(
    monkeypatch: pytest.MonkeyPatch, vault_api: VaultApiFake
) -> None:
    """With no usable token the Vault source names the token sources and asks nothing."""
    from devops_cli.security.secrets import reset_resolver

    for name in ("VAULT_TOKEN", "DEVOPS_CLI_VAULT_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:8200")
    reset_resolver()
    with pytest.raises(VaultAuthenticationError, match="devops vault login"):
        sync_repository_secrets("dan-petty/devops-cli", secret_names=["A"], source="vault")
    assert not vault_api.requested


def test_resolve_secret_unsupported_source() -> None:
    with pytest.raises(GitHubOperationError) as exc_info:
        sync_repository_secrets(
            "dan-petty/devops-cli", secret_names=["test"], source="unsupported_store"
        )
    assert "Unsupported secret source" in str(exc_info.value)


def test_sync_repository_secrets_empty_list() -> None:
    res = sync_repository_secrets("dan-petty/devops-cli", secret_names=[])
    assert len(res.synced_secrets) == 0
    assert len(res.missing_secrets) == 0


def test_sync_repository_secrets_missing_secret(process_fake: ProcessFake) -> None:
    res = sync_repository_secrets("dan-petty/devops-cli", secret_names=["NONEXISTENT"])
    assert "NONEXISTENT" in res.missing_secrets
    assert len(res.items) == 1
    assert res.items[0].status == "missing"


def test_sync_repository_secrets_dry_run(keyring_store: KeyringFake) -> None:
    keyring_store.set_password("devops-cli", "MY_SECRET", "dummy-secret-value")
    res = sync_repository_secrets("dan-petty/devops-cli", secret_names=["MY_SECRET"], dry_run=True)
    assert res.dry_run is True
    assert "MY_SECRET" in res.synced_secrets
    assert res.items[0].status == "synced"
    assert "dry-run" in res.items[0].message


def test_sync_repository_secrets_live_uploads_encrypted_payload(
    mock_keypair: tuple[str, public.PrivateKey],
    keyring_store: KeyringFake,
    process_fake: ProcessFake,
) -> None:
    pk_b64, _ = mock_keypair
    keyring_store.set_password("devops-cli", "SECRET_A", "live-secret-val")
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/actions/secrets/public-key"],
        ProcessAnswer(stdout=f'{{"key_id": "pk-1", "key": "{pk_b64}"}}'),
    )
    process_fake.answer(
        [
            "gh",
            "api",
            "-X",
            "PUT",
            "repos/dan-petty/devops-cli/actions/secrets/SECRET_A",
            "--input",
            "-",
        ],
        ProcessAnswer(stdout=""),
    )
    res = sync_repository_secrets("dan-petty/devops-cli", secret_names=["SECRET_A"], dry_run=False)
    assert "SECRET_A" in res.synced_secrets
    assert len(res.failed_secrets) == 0


def test_sync_repository_secrets_handles_upload_rejection(
    mock_keypair: tuple[str, public.PrivateKey],
    keyring_store: KeyringFake,
    process_fake: ProcessFake,
) -> None:
    pk_b64, _ = mock_keypair
    keyring_store.set_password("devops-cli", "SECRET_A", "live-secret-val")
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/actions/secrets/public-key"],
        ProcessAnswer(stdout=f'{{"key_id": "pk-1", "key": "{pk_b64}"}}'),
    )
    process_fake.answer(
        [
            "gh",
            "api",
            "-X",
            "PUT",
            "repos/dan-petty/devops-cli/actions/secrets/SECRET_A",
            "--input",
            "-",
        ],
        ProcessAnswer(returncode=1, stderr="Upload rejected"),
    )
    res = sync_repository_secrets("dan-petty/devops-cli", secret_names=["SECRET_A"], dry_run=False)
    assert "SECRET_A" in res.failed_secrets
    assert len(res.synced_secrets) == 0


def test_cli_secrets_list_displays_entries(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/actions/secrets"],
        ProcessAnswer(
            stdout='{"secrets": [{"name": "GITHUB_TOKEN"}, {"name": "DOCKER_PASSWORD"}]}'
        ),
    )
    res = cli("gh", "secrets", "list", "--repo", "dan-petty/devops-cli")
    assert res.exit_code == 0
    assert "GITHUB_TOKEN" in res.stdout
    assert "DOCKER_PASSWORD" in res.stdout


def test_cli_secrets_list_reports_empty_when_no_secrets(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/actions/secrets"],
        ProcessAnswer(stdout='{"secrets": []}'),
    )
    res = cli("gh", "secrets", "list", "--repo", "dan-petty/devops-cli")
    assert res.exit_code == 0
    assert "No repository secrets found" in res.stdout


def test_cli_secrets_sync_dry_run_previews_sync(
    cli: Callable[..., Any], keyring_store: KeyringFake
) -> None:
    keyring_store.set_password("devops-cli", "MY_TOKEN", "dummy-val")
    res = cli(
        "gh", "secrets", "sync", "-n", "MY_TOKEN", "--repo", "dan-petty/devops-cli", "--dry-run"
    )
    assert res.exit_code == 0
    assert "Plan for synchronizing secrets (dan-petty/devops-cli)" in res.stdout
    assert "gh api" in res.stdout


def test_cli_secrets_sync_failure_exit_on_upload_error(
    cli: Callable[..., Any],
    keyring_store: KeyringFake,
    mock_keypair: tuple[str, public.PrivateKey],
    process_fake: ProcessFake,
) -> None:
    pk_b64, _ = mock_keypair
    keyring_store.set_password("devops-cli", "FAIL_TOKEN", "fail-val")
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/actions/secrets/public-key"],
        ProcessAnswer(stdout=f'{{"key_id": "pk-1", "key": "{pk_b64}"}}'),
    )
    process_fake.answer(
        [
            "gh",
            "api",
            "-X",
            "PUT",
            "repos/dan-petty/devops-cli/actions/secrets/FAIL_TOKEN",
            "--input",
            "-",
        ],
        ProcessAnswer(returncode=1, stderr="Rejected"),
    )
    res = cli("gh", "secrets", "sync", "-n", "FAIL_TOKEN", "--repo", "dan-petty/devops-cli")
    assert res.exit_code == 1
    assert "Failed: 1" in res.stdout
