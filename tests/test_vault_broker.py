"""Unit tests for the HashiCorp Vault secret broker: token resolution, egress and reads."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.vault import app as vault_app
from devops_cli.config.constants import (
    CONST_HTTP_EGRESS_POLICY_EXTENSION,
    CONST_VAULT_LOGIN_KEYRING_KEY,
)
from devops_cli.config.settings import _EPHEMERAL_CI_SECRETS
from devops_cli.exceptions.vault import (
    VaultAuthenticationError,
    VaultKeyError,
    VaultOperationError,
)
from devops_cli.models.vault import VaultStoredLogin
from devops_cli.security.secrets import audit_entries, reset_resolver
from devops_cli.security.vault_broker import (
    VaultSecretBroker,
    parse_vault_uri,
)
from devops_cli.security.vault_lease import login_approle
from tests.web_fakes import StubWeb

runner = CliRunner()

VAULT_ADDR = "https://example.com:8200"
STORED_TOKEN = "s.stored-login-token"
ENV_TOKEN = "s.environment-token"
_REQUEST = "devops_cli.http.broker.HttpClientBroker.request"
_FALLBACK = "devops_cli.security.vault_broker.get_keyring_secret"


@pytest.fixture(autouse=True)
def _vault_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Start each test with no Vault token, address or namespace from the developer's shell."""
    for name in (
        "VAULT_ADDR",
        "DEVOPS_CLI_VAULT_ADDR",
        "VAULT_TOKEN",
        "DEVOPS_CLI_VAULT_TOKEN",
        "VAULT_NAMESPACE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VAULT_ADDR", VAULT_ADDR)
    reset_resolver()
    yield
    reset_resolver()


def store_login(
    monkeypatch: pytest.MonkeyPatch,
    vault_addr: str = VAULT_ADDR,
    namespace: str | None = None,
    token: str = STORED_TOKEN,
) -> None:
    """Put a `devops vault login` record in the in-process secret store for this test."""
    record = VaultStoredLogin(token=token, vault_addr=vault_addr, namespace=namespace)
    monkeypatch.setitem(
        _EPHEMERAL_CI_SECRETS, CONST_VAULT_LOGIN_KEYRING_KEY, record.model_dump_json()
    )


def reply(status: int = 200, payload: Any = None) -> httpx2.Response:
    """Build a Vault HTTP reply."""
    return httpx2.Response(status, json=payload if payload is not None else {})


def kv(fields: dict[str, Any]) -> httpx2.Response:
    """Build a KV-v2 read reply holding `fields`."""
    return reply(200, {"data": {"data": fields, "metadata": {"version": 1}}})


def vault_hops(stub_web: StubWeb) -> list[str]:
    """The requests the stub received for the Vault host, leaving out telemetry exports."""
    return [url for url in stub_web.requested if httpx2.URL(url).host == "example.com"]


def sent_tokens(mock_request: MagicMock) -> list[str | None]:
    """The X-Vault-Token header of every request the patched broker received."""
    return [call.kwargs["headers"].get("X-Vault-Token") for call in mock_request.call_args_list]


def test_parse_vault_uri() -> None:
    """Test parsing vault:// URIs into path and key components."""
    assert (
        parse_vault_uri("vault://secret/data/devops/creds#github_token"),
        parse_vault_uri("vault://secret/data/ci/database"),
        parse_vault_uri("secret/data/plain"),
    ) == (
        ("secret/data/devops/creds", "github_token"),
        ("secret/data/ci/database", None),
        ("secret/data/plain", None),
    )


def test_vault_broker_get_secret_api_success() -> None:
    """A token-carrying read returns Vault's field, or the whole secret, and names Vault."""
    broker = VaultSecretBroker(vault_addr=VAULT_ADDR, vault_token="s.test-token")
    fields = {"api_key": "vault-secret-value-xyz", "username": "admin"}

    with patch(_REQUEST, return_value=kv(fields)) as mock_request:
        one = broker.get_secret("secret/data/myapp", key="api_key")
        everything = broker.get_secret("secret/data/myapp")

    assert (one.value, one.source, one.checked, everything.value) == (
        "vault-secret-value-xyz",
        "vault",
        ["vault"],
        fields,
    )
    assert sent_tokens(mock_request) == ["s.test-token", "s.test-token"]


def test_vault_broker_set_secret_success() -> None:
    """A write posts the KV-v2 envelope with the token and returns without error."""
    broker = VaultSecretBroker(vault_addr=VAULT_ADDR, vault_token="s.test-token")

    with patch(_REQUEST, return_value=reply(200, {"data": {"version": 2}})) as mock_request:
        broker.set_secret("secret/data/myapp", {"token": "new-secret"})

    call = mock_request.call_args
    assert (call.args, call.kwargs["json"], sent_tokens(mock_request)) == (
        ("POST", f"{VAULT_ADDR}/v1/secret/data/myapp"),
        {"data": {"token": "new-secret"}},
        ["s.test-token"],
    )


def test_vault_broker_get_status() -> None:
    """Test querying Vault health status endpoint."""
    broker = VaultSecretBroker(vault_addr=VAULT_ADDR)
    health = {"initialized": True, "sealed": False, "version": "1.15.0", "cluster_name": "main"}

    with patch(_REQUEST, return_value=reply(200, health)):
        status = broker.get_status()

    assert (status.initialized, status.sealed, status.version, status.is_healthy) == (
        True,
        False,
        "1.15.0",
        True,
    )


def test_get_status_reports_an_unreachable_vault() -> None:
    """A health check that gets no answer becomes a sealed status naming the failure."""
    broker = VaultSecretBroker(vault_addr=VAULT_ADDR)

    with patch(_REQUEST, side_effect=httpx2.ConnectError("Connection refused")):
        status = broker.get_status()

    assert (status.sealed, "did not answer" in (status.error_message or "")) == (True, True)


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


def test_vault_broker_validates_address_scheme() -> None:
    with pytest.raises(ValueError, match="scheme"):
        VaultSecretBroker(vault_addr="ftp://example.com:8200")

    with pytest.raises(ValueError, match=r"traversal|format|invalid"):
        VaultSecretBroker(vault_addr="http://example.com/../traversal")


# ─────────────────────────────────────────────────────────────────────────────
# Token resolution
# ─────────────────────────────────────────────────────────────────────────────


def test_stored_login_supplies_the_token_when_the_environment_has_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no environment token, the stored login for this address is sent and reported."""
    store_login(monkeypatch)
    broker = VaultSecretBroker()

    with patch(_REQUEST, return_value=kv({"k": "v"})) as mock_request:
        broker.get_secret("secret/data/app", key="k")

    assert (broker.token_source.source, sent_tokens(mock_request)) == ("keyring", [STORED_TOKEN])


def test_keyring_outranks_the_environment_and_the_argument_outranks_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The order is argument, stored login, then the environment."""
    store_login(monkeypatch)
    monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)

    stored = VaultSecretBroker()
    argument = VaultSecretBroker(vault_token="s.argument")

    assert (stored.vault_token, stored.token_source.source) == (STORED_TOKEN, "keyring")
    assert (argument.vault_token, argument.token_source.source) == ("s.argument", "argument")


def test_devops_cli_vault_token_is_the_last_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """DEVOPS_CLI_VAULT_TOKEN answers when nothing before it does."""
    monkeypatch.setenv("DEVOPS_CLI_VAULT_TOKEN", ENV_TOKEN)
    broker = VaultSecretBroker()
    assert (broker.vault_token, broker.token_source.source) == (ENV_TOKEN, "environment")


@pytest.mark.parametrize(
    ("stored_addr", "stored_namespace", "issuer"),
    [
        ("https://example.com:8201", None, "https://example.com:8201"),
        (VAULT_ADDR, "team-b", f"{VAULT_ADDR} (namespace team-b)"),
    ],
)
def test_stored_login_for_another_vault_is_never_sent(
    monkeypatch: pytest.MonkeyPatch, stored_addr: str, stored_namespace: str | None, issuer: str
) -> None:
    """A login stored for another address or namespace is passed over, naming its issuer."""
    store_login(monkeypatch, vault_addr=stored_addr, namespace=stored_namespace)

    without_env = VaultSecretBroker()
    with pytest.raises(VaultAuthenticationError) as no_token:
        without_env.require_token()

    monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)
    reset_resolver()
    with_env = VaultSecretBroker()
    with patch(_REQUEST, return_value=kv({"k": "v"})) as mock_request:
        with_env.get_secret("secret/data/app", key="k")

    assert (without_env.vault_token, without_env.token_source.source) == (None, "none")
    assert f"issued for {issuer}" in no_token.value.message
    assert (with_env.token_source.source, sent_tokens(mock_request)) == (
        "environment",
        [ENV_TOKEN],
    )
    assert with_env.token_source.stored_login_skipped == f"issued for {issuer}"


def test_a_bare_token_entry_is_unusable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A token stored before the login record existed is not sent; the user is told to log in."""
    monkeypatch.setitem(_EPHEMERAL_CI_SECRETS, CONST_VAULT_LOGIN_KEYRING_KEY, "s.bare-token")
    broker = VaultSecretBroker()

    with pytest.raises(VaultAuthenticationError) as no_token:
        broker.require_token()

    assert broker.vault_token is None
    assert "run `devops vault login` again" in no_token.value.message


def test_no_token_message_names_every_source() -> None:
    """With no token anywhere, the error names the login command and both variables."""
    with pytest.raises(VaultAuthenticationError) as no_token:
        VaultSecretBroker().require_token()

    message = no_token.value.message
    assert all(
        name in message for name in ("devops vault login", "VAULT_TOKEN", "DEVOPS_CLI_VAULT_TOKEN")
    )


def test_a_locked_keyring_reads_as_no_stored_token(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A locked keyring hides the stored login: the broker has no token and the lock is logged."""
    from keyring.errors import KeyringLocked

    monkeypatch.setattr("devops_cli.config.settings._ensure_keyring_backend", lambda: True)
    with (
        patch("keyring.get_password", side_effect=KeyringLocked("locked")),
        caplog.at_level(logging.WARNING, logger="devops_cli.config.settings"),
    ):
        broker = VaultSecretBroker()

    assert (broker.vault_token, broker.token_source.source) == (None, "none")
    assert "keyring is locked" in caplog.text


def test_token_lookups_are_audited_by_name_never_by_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """`devops vault audit` shows each token lookup the broker made, and no token."""
    monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)
    VaultSecretBroker()

    entries = [(e.credential_id, e.provider, e.resolved) for e in audit_entries()]
    assert entries == [("vault.login", None, False), ("vault.token", "environment", True)]
    assert all(ENV_TOKEN not in repr(entry) for entry in audit_entries())


def test_stored_login_never_reprs_its_token() -> None:
    """The record keeps the token out of its repr."""
    record = VaultStoredLogin(token=STORED_TOKEN, vault_addr=VAULT_ADDR)
    assert STORED_TOKEN not in repr(record)


# ─────────────────────────────────────────────────────────────────────────────
# Where a token is sent
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("source", ["stored", "environment"])
def test_status_never_sends_a_token(monkeypatch: pytest.MonkeyPatch, source: str) -> None:
    """`sys/health` needs no token, so status sends none, whatever address it is given."""
    store_login(monkeypatch, vault_addr="https://example.com")
    if source == "environment":
        monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)

    with patch(_REQUEST, return_value=reply(200, {"initialized": True})) as mock_request:
        res = runner.invoke(vault_app, ["status", "--addr", "https://example.com"])

    assert (res.exit_code, sent_tokens(mock_request)) == (0, [None])


def test_every_vault_request_carries_the_same_origin_policy() -> None:
    """The broker hands each request an egress policy for its own Vault origin."""
    broker = VaultSecretBroker(vault_addr=VAULT_ADDR, vault_token="s.t")

    with patch(_REQUEST, return_value=kv({"k": "v"})) as mock_request:
        broker.get_secret("secret/data/app", key="k")

    policy = mock_request.call_args.kwargs["extensions"][CONST_HTTP_EGRESS_POLICY_EXTENSION]
    policy(f"{VAULT_ADDR}/v1/other")
    with pytest.raises(VaultOperationError, match=re.escape("https://example.com:8443")):
        policy("https://example.com:8443/v1/secret/data/app")


def test_a_redirect_to_another_origin_is_refused(stub_web: StubWeb) -> None:
    """A 307 to another port is refused before the token reaches it."""
    stub_web.redirect(
        f"{VAULT_ADDR}/v1/secret/data/app",
        "https://example.com:8443/v1/secret/data/app",
        status=307,
    )
    broker = VaultSecretBroker(vault_addr=VAULT_ADDR, vault_token="s.t")

    with patch(_FALLBACK) as keyring_fallback:
        with pytest.raises(
            VaultOperationError, match=re.escape("https://example.com:8443")
        ) as refused:
            broker.get_secret("secret/data/app", key="k")

    assert vault_hops(stub_web) == [f"{VAULT_ADDR}/v1/secret/data/app"]
    assert "nothing was sent there" in refused.value.message
    keyring_fallback.assert_not_called()


def test_a_login_body_never_follows_a_redirect_to_another_origin(stub_web: StubWeb) -> None:
    """A 307 keeps the POST body, so an AppRole login redirected elsewhere is refused."""
    stub_web.redirect(
        f"{VAULT_ADDR}/v1/auth/approle/login",
        "https://example.com:8443/v1/auth/approle/login",
        status=307,
    )

    with pytest.raises(VaultOperationError, match=re.escape("https://example.com:8443")):
        login_approle(VAULT_ADDR, "role", "secret-id")

    assert vault_hops(stub_web) == [f"{VAULT_ADDR}/v1/auth/approle/login"]


def test_a_same_origin_redirect_is_followed(stub_web: StubWeb) -> None:
    """A redirect within the Vault origin is still followed."""
    stub_web.redirect(f"{VAULT_ADDR}/v1/secret/data/old", f"{VAULT_ADDR}/v1/secret/data/new", 307)
    stub_web.page(
        f"{VAULT_ADDR}/v1/secret/data/new",
        '{"data": {"data": {"k": "moved"}}}',
        headers={"content-type": "application/json"},
    )
    broker = VaultSecretBroker(vault_addr=VAULT_ADDR, vault_token="s.t")

    lookup = broker.get_secret("secret/data/old", key="k")

    assert (lookup.value, lookup.source, vault_hops(stub_web)) == (
        "moved",
        "vault",
        [f"{VAULT_ADDR}/v1/secret/data/old", f"{VAULT_ADDR}/v1/secret/data/new"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Missing or rejected tokens and Vault-only reads
# ─────────────────────────────────────────────────────────────────────────────


def test_writes_and_syncs_without_a_token_make_no_request() -> None:
    """With no usable token, set and sync raise before any request."""
    broker = VaultSecretBroker()

    with patch(_REQUEST) as mock_request:
        with pytest.raises(VaultAuthenticationError):
            broker.set_secret("secret/data/app", {"k": "v"})
        with pytest.raises(VaultAuthenticationError):
            broker.sync_to_keyring("secret/data/app")

    mock_request.assert_not_called()


@pytest.mark.parametrize("status", [401, 403])
def test_a_rejected_token_raises_and_never_falls_back(status: int) -> None:
    """Vault refusing the token is an error naming its source and status, not a keyring read."""
    broker = VaultSecretBroker(vault_token="s.expired")

    with patch(_REQUEST, return_value=reply(status)), patch(_FALLBACK) as keyring_fallback:
        with pytest.raises(VaultAuthenticationError) as rejected:
            broker.get_secret("secret/data/app", key="k")

    message = rejected.value.message
    assert (f"HTTP {status}" in message, "from the argument" in message) == (True, True)
    assert all(hint in message for hint in ("expired", "revoked", "no policy", "vault login"))
    keyring_fallback.assert_not_called()


def test_other_refusals_raise_with_the_status() -> None:
    """A sealed or failing Vault answers with an error, never a keyring fallback."""
    broker = VaultSecretBroker(vault_token="s.t")

    with patch(_REQUEST, return_value=reply(503)), patch(_FALLBACK) as keyring_fallback:
        with pytest.raises(VaultOperationError, match="HTTP 503"):
            broker.get_secret("secret/data/app", key="k")
        with pytest.raises(VaultOperationError, match="HTTP 503"):
            broker.set_secret("secret/data/app", {"k": "v"})

    keyring_fallback.assert_not_called()


def test_a_body_without_secret_data_is_an_error() -> None:
    """A 200 reply that holds no secret data is refused rather than read as empty."""
    broker = VaultSecretBroker(vault_token="s.t")

    with patch(_REQUEST, return_value=httpx2.Response(200, content=b"not json")):
        with pytest.raises(VaultOperationError, match="not JSON"):
            broker.read_secret("secret/data/app")
    with patch(_REQUEST, return_value=reply(200, {"data": "flat"})):
        with pytest.raises(VaultOperationError, match="without secret data"):
            broker.read_secret("secret/data/app")


@pytest.mark.parametrize(
    ("vault_reply", "reason"),
    [
        (reply(404), "Vault has no value at 'secret/data/app' for 'k'"),
        (kv({"other": "x"}), "Vault has no value at 'secret/data/app' for 'k'"),
    ],
)
def test_no_value_in_vault_falls_back_to_the_keyring(
    vault_reply: httpx2.Response, reason: str
) -> None:
    """With a token, a path or field Vault lacks is answered from the keyring, which is named."""
    broker = VaultSecretBroker(vault_token="s.t")

    with patch(_REQUEST, return_value=vault_reply), patch(_FALLBACK, return_value="cached"):
        lookup = broker.get_secret("secret/data/app", key="k")

    assert (lookup.value, lookup.source, lookup.checked, lookup.fallback_reason) == (
        "cached",
        "keyring",
        ["vault", "keyring"],
        reason,
    )


def test_an_unreachable_vault_falls_back_to_the_keyring() -> None:
    """A Vault that does not answer leaves the keyring to answer, saying why."""
    broker = VaultSecretBroker(vault_token="s.t")

    with (
        patch(_REQUEST, side_effect=httpx2.ConnectError("refused")),
        patch(_FALLBACK, return_value="cached"),
    ):
        lookup = broker.get_secret("secret/data/app", key="k")

    assert (lookup.source, "did not answer" in (lookup.fallback_reason or "")) == (
        "keyring",
        True,
    )


def test_without_a_token_only_the_keyring_is_checked() -> None:
    """No usable token means Vault is not consulted, and the lookup says so."""
    broker = VaultSecretBroker()

    with patch(_REQUEST) as mock_request, patch(_FALLBACK, return_value=None):
        lookup = broker.get_secret("secret/data/app", key="k")

    assert (lookup.value, lookup.checked, lookup.fallback_reason) == (
        None,
        ["keyring"],
        "Vault was not consulted: no usable token",
    )
    mock_request.assert_not_called()


def test_sync_reads_vault_alone_and_never_writes_the_login_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync stores Vault's fields, skips the login record's name, and reports what it lacks."""
    store_login(monkeypatch)
    stored_record = _EPHEMERAL_CI_SECRETS[CONST_VAULT_LOGIN_KEYRING_KEY]
    broker = VaultSecretBroker(vault_namespace=None)
    fields = {"api_key": "v1", "db_pass": "v2", CONST_VAULT_LOGIN_KEYRING_KEY: "s.attacker"}

    with (
        patch(_REQUEST, return_value=kv(fields)),
        patch("devops_cli.security.vault_broker.set_keyring_secret", return_value=True) as store,
    ):
        everything = broker.sync_to_keyring("secret/data/app")
        chosen = broker.sync_to_keyring("secret/data/app", keys=["api_key", "absent"])

    assert (everything.synced, everything.skipped, chosen.synced, chosen.missing) == (
        ["api_key", "db_pass"],
        [CONST_VAULT_LOGIN_KEYRING_KEY],
        ["api_key"],
        ["absent"],
    )
    assert [call.args[0] for call in store.call_args_list] == ["api_key", "db_pass", "api_key"]
    assert _EPHEMERAL_CI_SECRETS[CONST_VAULT_LOGIN_KEYRING_KEY] == stored_record


def test_sync_of_a_path_with_no_secret_is_an_error() -> None:
    """Syncing a path Vault has nothing at fails instead of reporting zero secrets."""
    broker = VaultSecretBroker(vault_token="s.t")

    with patch(_REQUEST, return_value=reply(404)):
        with pytest.raises(VaultKeyError, match="no secret at 'secret/data/app'"):
            broker.sync_to_keyring("secret/data/app")


def test_namespace_header_travels_with_the_token() -> None:
    """A namespaced broker sends its namespace beside the token."""
    broker = VaultSecretBroker(vault_token="s.t", vault_namespace="admin/ns")

    with patch(_REQUEST, return_value=kv({"k": "v"})) as mock_request:
        broker.read_secret("secret/data/app", key="k")

    headers = mock_request.call_args.kwargs["headers"]
    assert (headers["X-Vault-Token"], headers["X-Vault-Namespace"]) == ("s.t", "admin/ns")
