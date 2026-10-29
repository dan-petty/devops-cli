"""`revoke_lease` revokes one Vault lease with the broker's token and maps each refusal to the
error that names its cause (#2543)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from devops_cli.exceptions.vault import VaultAuthenticationError, VaultLeaseError
from devops_cli.security.secrets import reset_resolver
from devops_cli.security.vault_broker import VaultSecretBroker
from devops_cli.security.vault_lease import reset_lease_registry, revoke_lease
from tests.web_fakes import StubWeb

VAULT_ADDR = "https://example.com:8200"
REVOKE_URL = f"{VAULT_ADDR}/v1/sys/leases/revoke"
TOKEN = "s.environment-token"

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture
def broker(monkeypatch: pytest.MonkeyPatch) -> Iterator[VaultSecretBroker]:
    """A broker for one Vault address, with its token from the environment."""
    for name in ("DEVOPS_CLI_VAULT_ADDR", "DEVOPS_CLI_VAULT_TOKEN", "VAULT_NAMESPACE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VAULT_ADDR", VAULT_ADDR)
    monkeypatch.setenv("VAULT_TOKEN", TOKEN)
    reset_resolver()
    reset_lease_registry()
    yield VaultSecretBroker()
    reset_resolver()
    reset_lease_registry()


def test_a_revoke_sends_the_lease_id_with_the_token(
    stub_web: StubWeb, broker: VaultSecretBroker
) -> None:
    stub_web.respond("POST", REVOKE_URL, 204)

    revoke_lease(broker, "database/creds/app/lease-1")

    sent = stub_web.sent[-1]
    assert (
        sent.method,
        str(sent.url),
        json.loads(sent.content),
        sent.headers["X-Vault-Token"],
    ) == (
        "POST",
        REVOKE_URL,
        {"lease_id": "database/creds/app/lease-1"},
        TOKEN,
    )


def test_a_rejected_token_names_its_source_and_the_login_command(
    stub_web: StubWeb, broker: VaultSecretBroker
) -> None:
    stub_web.respond("POST", REVOKE_URL, 403, {"errors": ["permission denied"]})

    with pytest.raises(VaultAuthenticationError) as caught:
        revoke_lease(broker, "lease-1")

    message = str(caught.value)
    assert ("from the environment (HTTP 403)" in message, "devops vault login" in message) == (
        True,
        True,
    )


def test_another_refusal_names_the_masked_lease_and_the_status(
    stub_web: StubWeb, broker: VaultSecretBroker
) -> None:
    secret = "ghp_" + "a1B2c3D4e5" * 4
    stub_web.respond("POST", REVOKE_URL, 400, {"errors": ["invalid lease"]})

    with pytest.raises(VaultLeaseError) as caught:
        revoke_lease(broker, f"auth/token/{secret}")

    message = str(caught.value)
    assert (caught.value.status_code, "status 400" in message, secret in message) == (
        400,
        True,
        False,
    )
