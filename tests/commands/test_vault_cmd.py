"""Unit tests for HashiCorp Vault enterprise secret broker CLI commands."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from typer.testing import CliRunner

import devops_cli.main  # noqa: F401  # loaded here, not in a test: MCP dispatches through it
from devops_cli.ai.mcp.server import vault_status
from devops_cli.commands.vault import _validate_vault_path, app
from devops_cli.config.constants import CONST_VAULT_LOGIN_KEYRING_KEY
from devops_cli.config.os_keyring import (
    KeyringLockedError,
    KeyringUnavailableError,
    get_keyring_secret,
    remember_secret,
)
from devops_cli.exceptions.vault import VaultOperationError
from devops_cli.models.vault import (
    VaultSecretLookup,
    VaultStoredLogin,
    VaultSyncReport,
    VaultTokenSource,
)
from devops_cli.security.secrets import reset_resolver
from devops_cli.security.vault_broker import VaultStatus
from tests.web_fakes import PUBLIC_ADDRESS, http_response, record_connects, scripted_resolver


def reset_lease_registry() -> None:
    from devops_cli.security import vault_lease

    fn = getattr(vault_lease, "reset_lease_registry", None)
    if fn is not None:
        fn()


pytestmark = pytest.mark.usefixtures("keyring_store")

runner = CliRunner()

VAULT_ADDR = "https://example.com:8200"
STORED_TOKEN = "s.stored-login-token"
ENV_TOKEN = "s.environment-token"
_REQUEST = "devops_cli.http.broker.HttpClientBroker.request"
_FALLBACK = "devops_cli.security.vault_broker.get_keyring_secret"
_TOKEN_SOURCES = ("devops vault login", "VAULT_TOKEN", "DEVOPS_CLI_VAULT_TOKEN")


@pytest.fixture(autouse=True)
def _vault_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Start each test at one Vault address, with no token and no session lease registry."""
    for name in (
        "DEVOPS_CLI_VAULT_ADDR",
        "VAULT_TOKEN",
        "DEVOPS_CLI_VAULT_TOKEN",
        "VAULT_NAMESPACE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VAULT_ADDR", VAULT_ADDR)
    reset_resolver()
    reset_lease_registry()
    yield
    reset_resolver()
    reset_lease_registry()


def _record(vault_addr: str = VAULT_ADDR, namespace: str | None = None) -> str:
    """Serialize a `devops vault login` record."""
    return VaultStoredLogin(
        token=STORED_TOKEN, vault_addr=vault_addr, namespace=namespace
    ).model_dump_json()


def store_login(monkeypatch: pytest.MonkeyPatch, vault_addr: str = VAULT_ADDR) -> None:
    """Put a login record in the in-process secret store for this test."""
    remember_secret(CONST_VAULT_LOGIN_KEYRING_KEY, _record(vault_addr))


def reply(status: int = 200, payload: Any = None) -> httpx2.Response:
    """Build a Vault HTTP reply."""
    return httpx2.Response(status, json=payload if payload is not None else {})


def _mock_broker(**attributes: Any) -> MagicMock:
    """A broker double with a real token source, for tests of the command's rendering."""
    broker = MagicMock()
    broker.vault_addr = "http://example.com:8200"
    broker.token_source = VaultTokenSource(source="environment")
    for name, value in attributes.items():
        setattr(broker, name, value)
    return broker


# ─────────────────────────────────────────────────────────────────────────────
# Path validation
# ─────────────────────────────────────────────────────────────────────────────


def test_validate_vault_path_valid() -> None:
    assert _validate_vault_path("secret/data/myapp") is None
    assert _validate_vault_path("vault://secret/data/myapp#token") is None
    assert _validate_vault_path("secret/my-app_1/api-key") is None


def test_validate_vault_path_empty_error() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        _validate_vault_path("   ")


def test_validate_vault_path_traversal_error() -> None:
    with pytest.raises(ValueError, match="cannot contain '\\.\\.' traversal"):
        _validate_vault_path("secret/../../etc/passwd")


def test_validate_vault_path_invalid_characters() -> None:
    with pytest.raises(ValueError, match="contains invalid characters"):
        _validate_vault_path("secret/myapp;rm -rf /")


@pytest.mark.parametrize("command", [["get"], ["set", "KEY=VAL"], ["sync"]])
def test_invalid_paths_are_refused(command: list[str]) -> None:
    res = runner.invoke(app, [command[0], "path/../bad", *command[1:]])
    assert (res.exit_code, "traversal" in res.output) == (1, True)


# ─────────────────────────────────────────────────────────────────────────────
# vault status
# ─────────────────────────────────────────────────────────────────────────────


def test_vault_status_healthy() -> None:
    status = VaultStatus(initialized=True, sealed=False, version="1.15.2", cluster_name="main")
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        mock_cls.return_value = _mock_broker(get_status=MagicMock(return_value=status))
        res = runner.invoke(app, ["status", "--addr", "http://example.com:8200"])

    assert res.exit_code == 0
    assert all(text in res.output for text in ("Vault Address", "1.15.2", "Healthy", "Token"))


def test_vault_status_degraded_with_error() -> None:
    status = VaultStatus(error_message="Connection refused to cluster port 8200")
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        mock_cls.return_value = _mock_broker(get_status=MagicMock(return_value=status))
        res = runner.invoke(app, ["status"])

    assert res.exit_code == 0
    assert all(text in res.output for text in ("Connection refused", "Sealed", "Degraded"))


def test_vault_status_names_the_stored_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """After a login, status shows the token comes from the keyring."""
    store_login(monkeypatch)
    with patch(_REQUEST, return_value=reply(200, {"initialized": True})):
        res = runner.invoke(app, ["status"])
    assert (res.exit_code, bool(re.search(r"Token\s+keyring", res.output))) == (0, True)


def test_vault_status_names_the_address_a_skipped_token_was_issued_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With VAULT_ADDR moved elsewhere, status says the stored token is not used and why."""
    store_login(monkeypatch)
    monkeypatch.setenv("VAULT_ADDR", "https://example.com:8201")
    with patch(_REQUEST, return_value=reply(200, {"initialized": True})):
        res = runner.invoke(app, ["status"])
    assert res.exit_code == 0
    assert f"none (stored token not used: issued for {VAULT_ADDR})" in res.output


@pytest.mark.parametrize("source", ["stored", "environment"])
def test_mcp_vault_status_never_sends_a_token(monkeypatch: pytest.MonkeyPatch, source: str) -> None:
    """The health request carries no token, whether it comes from the keyring or the environment."""
    store_login(monkeypatch)
    if source == "environment":
        monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)

    with patch(_REQUEST, return_value=reply(200, {"initialized": True})) as mock_request:
        vault_status()

    assert [
        call.kwargs["headers"].get("X-Vault-Token") for call in mock_request.call_args_list
    ] == [None]


HEALTH_ANSWER = json.dumps(
    {"initialized": True, "sealed": False, "version": "1.15.2", "cluster_name": "cluster-2639"}
)
"""A `sys/health` answer that holds the two fields the tool prints."""


async def _call_status_tool(arguments: dict[str, object]) -> tuple[bool, str]:
    """Call `vault_status` the way an MCP client does: whether the call failed, and its reply."""
    from fastmcp import Client

    from devops_cli.ai.mcp.server import mcp

    async with Client(mcp) as client:
        await client.call_tool("hydrate_tool_domain", {"domain": "vault"})
        result = await client.call_tool("vault_status", arguments, raise_on_error=False)
    return bool(result.is_error), "\n".join(getattr(block, "text", "") for block in result.content)


class TestStatusToolTakesNoAddressFromTheModel:
    """The MCP tool `vault_status` reports the configured Vault, never an address that the calling
    model gives (#2639)."""

    async def test_the_tool_publishes_no_address_parameter(self) -> None:
        """The schema holds `dry_run` and no Vault address."""
        from fastmcp import Client

        from devops_cli.ai.mcp.server import mcp

        async with Client(mcp) as client:
            await client.call_tool("hydrate_tool_domain", {"domain": "vault"})
            tools = await client.list_tools()

        assert [
            list(tool.input_schema["properties"]) for tool in tools if tool.name == "vault_status"
        ] == [["dry_run"]]

    async def test_an_address_argument_is_refused_and_reaches_no_socket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A call that gives an address fails and sends no request, and no answer comes back.

        On `origin/main` the client dialled `127.0.0.1:8200`, wrote
        `GET /some/path?x=/v1/sys/health`, and the reply held the `version` and `cluster_name`
        values of the answer.
        """
        scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})
        recorder = record_connects(monkeypatch, [http_response(200, HEALTH_ANSWER)] * 4)

        failed, reply_text = await _call_status_tool(
            {"vault_addr": "http://127.0.0.1:8200/some/path?x="}
        )

        assert (
            failed,
            "1. Parameter: `vault_addr`\n   Kind: HALLUCINATED_PARAM\n" in reply_text,
            "cluster-2639" in reply_text,
            [dial for dial in recorder.dialled if dial[1] == 8200],
            recorder.written,
        ) == (True, True, False, [], [])

    async def test_a_call_with_no_address_asks_the_configured_vault(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The request goes to `VAULT_ADDR`, and its path is `/v1/sys/health`."""
        scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})
        monkeypatch.setenv("VAULT_ADDR", "http://example.com:8200")
        recorder = record_connects(monkeypatch, [http_response(200, HEALTH_ANSWER)])

        failed, reply_text = await _call_status_tool({})

        vault = [
            bytes(written).split(b" HTTP/1.1")[0]
            for dialled, written in zip(recorder.dialled, recorder.written, strict=True)
            if dialled == (PUBLIC_ADDRESS, 8200)
        ]
        assert (failed, vault, "cluster-2639" in reply_text) == (
            False,
            [b"GET /v1/sys/health"],
            True,
        )

    async def test_a_call_with_no_configured_vault_names_the_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no `VAULT_ADDR` and no `DEVOPS_CLI_VAULT_ADDR`, the tool fails and names both."""
        monkeypatch.delenv("VAULT_ADDR")
        recorder = record_connects(monkeypatch, [http_response(200, HEALTH_ANSWER)])

        failed, reply_text = await _call_status_tool({})

        assert (
            failed,
            "VAULT_ADDR" in reply_text and "DEVOPS_CLI_VAULT_ADDR" in reply_text,
            "--vault-addr" in reply_text,
            [dial for dial in recorder.dialled if dial[1] == 8200],
        ) == (True, True, False, [])


def test_the_command_keeps_its_address_option(monkeypatch: pytest.MonkeyPatch) -> None:
    """A person who types `--addr` still names the Vault that the command asks."""
    scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})
    recorder = record_connects(monkeypatch, [http_response(200, HEALTH_ANSWER)])

    res = runner.invoke(app, ["status", "--addr", "http://example.com:8201"])

    assert (res.exit_code, [dial for dial in recorder.dialled if dial[0] == PUBLIC_ADDRESS]) == (
        0,
        [(PUBLIC_ADDRESS, 8201)],
    )


# ─────────────────────────────────────────────────────────────────────────────
# vault get
# ─────────────────────────────────────────────────────────────────────────────


def test_vault_get_not_found_names_only_the_sources_checked() -> None:
    """With no token, the not-found message names the keyring alone and says Vault was skipped."""
    with patch(_REQUEST) as mock_request, patch(_FALLBACK, return_value=None):
        res = runner.invoke(app, ["get", "secret/data/missing"])

    assert res.exit_code == 1
    assert "checked: keyring; Vault was not consulted: no usable token" in res.output
    mock_request.assert_not_called()


def test_vault_get_dict_masked_and_show() -> None:
    lookup = VaultSecretLookup(
        value={"api_key": "supersecret123", "db_password": "mypassword"},
        source="vault",
        checked=["vault"],
    )
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        mock_cls.return_value = _mock_broker(get_secret=MagicMock(return_value=lookup))
        masked = runner.invoke(app, ["get", "secret/data/myapp"])
        shown = runner.invoke(app, ["get", "secret/data/myapp", "--show"])

    assert (masked.exit_code, "***REDACTED***" in masked.output) == (0, True)
    assert "supersecret123" not in masked.output
    assert re.search(r"\(from\s+vault\)", masked.output)
    assert (shown.exit_code, "supersecret123" in shown.output) == (0, True)


def test_vault_get_scalar_masked_and_show() -> None:
    lookup = VaultSecretLookup(value="token_value_xyz", source="vault", checked=["vault"])
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        mock_cls.return_value = _mock_broker(get_secret=MagicMock(return_value=lookup))
        masked = runner.invoke(app, ["get", "secret/data/myapp", "--key", "token"])
        shown = runner.invoke(app, ["get", "secret/data/myapp", "--key", "token", "--show"])

    assert (masked.exit_code, "***REDACTED***" in masked.output) == (0, True)
    assert (shown.exit_code, "token (from vault): token_value_xyz" in shown.output) == (0, True)


def test_vault_get_answers_from_vault_with_the_stored_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a login, get reads Vault with the stored token and says Vault answered."""
    store_login(monkeypatch)
    with patch(_REQUEST, return_value=reply(200, {"data": {"data": {"k": "v"}}})) as mock_request:
        res = runner.invoke(app, ["get", "secret/data/app", "--key", "k", "--show"])

    assert (res.exit_code, "k (from vault): v" in res.output) == (0, True)
    assert mock_request.call_args.kwargs["headers"]["X-Vault-Token"] == STORED_TOKEN


def test_vault_get_on_a_rejected_token_exits_without_reading_the_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 403 is reported with its source and status; the keyring fallback is not read."""
    monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)
    with patch(_REQUEST, return_value=reply(403)), patch(_FALLBACK) as keyring_fallback:
        res = runner.invoke(app, ["get", "secret/data/app", "--key", "k"])

    assert res.exit_code == 1
    assert "Vault rejected the token from the environment (HTTP 403)" in res.output
    keyring_fallback.assert_not_called()


def test_vault_get_on_a_404_answers_from_the_keyring_and_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)
    with patch(_REQUEST, return_value=reply(404)), patch(_FALLBACK, return_value="cached"):
        res = runner.invoke(app, ["get", "secret/data/app", "--key", "k", "--show"])

    assert res.exit_code == 0
    assert "k (from keyring): cached" in res.output
    assert "Answered from the OS keyring: Vault has no value at 'secret/data/app'" in res.output


# ─────────────────────────────────────────────────────────────────────────────
# vault set and vault sync
# ─────────────────────────────────────────────────────────────────────────────


def test_vault_set_no_valid_pairs() -> None:
    res = runner.invoke(app, ["set", "secret/data/myapp", "invalid_no_equal_sign"])
    assert res.exit_code == 1
    assert "No valid KEY=VALUE pairs" in res.output


def test_vault_set_success() -> None:
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        mock_cls.return_value = _mock_broker()
        res = runner.invoke(app, ["set", "secret/data/myapp", "KEY1=VAL1", "KEY2=VAL2"])
    assert (res.exit_code, "Successfully stored 2 secret(s)" in res.output) == (0, True)


def test_vault_set_failure_reports_the_status() -> None:
    error = VaultOperationError("Vault answered HTTP 500 for 'secret/data/myapp'.")
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        mock_cls.return_value = _mock_broker(set_secret=MagicMock(side_effect=error))
        res = runner.invoke(app, ["set", "secret/data/myapp", "KEY=VAL"])
    assert (res.exit_code, "HTTP 500" in res.output) == (1, True)


@pytest.mark.parametrize(
    "command",
    [
        ["set", "secret/data/app", "KEY=VAL"],
        ["sync", "secret/data/app"],
        ["leases", "--revoke", "lease-1"],
    ],
)
def test_commands_needing_a_token_exit_before_any_request_without_one(command: list[str]) -> None:
    """With no usable token, set, sync and leases --revoke name the token sources and stop."""
    with patch(_REQUEST) as mock_request:
        res = runner.invoke(app, command)

    assert res.exit_code == 1
    assert all(source in res.output for source in _TOKEN_SOURCES)
    mock_request.assert_not_called()


def test_vault_sync_success() -> None:
    report = VaultSyncReport(synced=["k1", "k2", "k3"])
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        broker = _mock_broker(sync_to_keyring=MagicMock(return_value=report))
        mock_cls.return_value = broker
        res = runner.invoke(app, ["sync", "secret/data/myapp", "--key", "k1", "--key", "k2"])

    assert (res.exit_code, "Synchronized 3 secret(s)" in res.output) == (0, True)
    broker.sync_to_keyring.assert_called_once_with("secret/data/myapp", keys=["k1", "k2"])


def test_vault_sync_reports_the_skipped_login_key_and_missing_fields() -> None:
    report = VaultSyncReport(
        synced=["k1"], skipped=[CONST_VAULT_LOGIN_KEYRING_KEY], missing=["absent"]
    )
    with patch("devops_cli.commands.vault.VaultSecretBroker") as mock_cls:
        mock_cls.return_value = _mock_broker(sync_to_keyring=MagicMock(return_value=report))
        res = runner.invoke(app, ["sync", "secret/data/myapp"])

    assert res.exit_code == 1
    assert f"Skipped {CONST_VAULT_LOGIN_KEYRING_KEY}" in res.output
    assert "Vault has no value for: absent" in res.output


def test_vault_sync_of_an_empty_path_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """A path with no secret fails instead of reporting zero secrets synchronized."""
    monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)
    with patch(_REQUEST, return_value=reply(404)):
        res = runner.invoke(app, ["sync", "secret/data/app"])
    assert (res.exit_code, "Vault has no secret at 'secret/data/app'" in res.output) == (1, True)


# ─────────────────────────────────────────────────────────────────────────────
# Dry runs
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "command",
    [
        ["get", "secret/data/app", "--dry-run"],
        ["set", "secret/data/app", "FOO=BAR", "--dry-run"],
        ["sync", "secret/data/app", "-k", "token", "--dry-run"],
        ["leases", "--revoke", "lease-1"],
    ],
)
@pytest.mark.parametrize("token_env", [None, ENV_TOKEN])
def test_dry_runs_name_the_token_source_and_make_no_request(
    monkeypatch: pytest.MonkeyPatch, command: list[str], token_env: str | None
) -> None:
    """A dry run prints planned requests and sends nothing."""
    if token_env:
        monkeypatch.setenv("VAULT_TOKEN", token_env)
    with patch(_REQUEST) as mock_request:
        res = runner.invoke(app, command, env={"DEVOPS_CLI_DRY_RUN": "true"})

    assert (res.exit_code, "Planned requests for devops vault" in res.output) == (0, True)
    mock_request.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# vault leases
# ─────────────────────────────────────────────────────────────────────────────


def test_leases_revoke_succeeds_with_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)
    with patch(_REQUEST, return_value=httpx2.Response(204)) as mock_request:
        res = runner.invoke(app, ["leases", "--revoke", "lease-1"])

    assert (res.exit_code, "Revoked lease" in res.output) == (0, True)
    assert mock_request.call_args.kwargs["headers"]["X-Vault-Token"] == ENV_TOKEN


def test_leases_revoke_refusal_names_the_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)
    with patch(_REQUEST, return_value=reply(400)):
        res = runner.invoke(app, ["leases", "--revoke", "lease-1"])
    assert (res.exit_code, "status 400" in res.output) == (1, True)


def test_leases_revoke_with_a_rejected_token_names_its_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)
    with patch(_REQUEST, return_value=reply(403)):
        res = runner.invoke(app, ["leases", "--revoke", "lease-1"])
    assert res.exit_code == 1
    assert "Vault rejected the token from the environment (HTTP 403)" in res.output


def test_leases_without_revoke_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running vault leases without --revoke fails with a usage error."""
    monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)
    res = runner.invoke(app, ["leases"])
    assert res.exit_code != 0
    assert "Missing option '--revoke'" in res.output or "Missing option" in res.output


def test_leases_renew_flag_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The removed --renew flag is rejected as an unknown option."""
    monkeypatch.setenv("VAULT_TOKEN", ENV_TOKEN)
    res = runner.invoke(app, ["leases", "--renew"])
    assert res.exit_code != 0
    assert "No such option: --renew" in res.output or "no such option" in res.output.lower()


# ─────────────────────────────────────────────────────────────────────────────
# vault login
# ─────────────────────────────────────────────────────────────────────────────


_LOGIN = ["login", "--role-id", "role", "--secret-id", "secret-id"]
_LOGIN_REPLY = {
    "auth": {
        "client_token": "s.issued",
        "accessor": "acc",
        "lease_duration": 3600,
        "renewable": True,
        "policies": ["default"],
    }
}


@pytest.fixture
def usable_keyring() -> Iterator[MagicMock]:
    """An unlocked, encrypted keyring whose writes are recorded."""
    with (
        patch("devops_cli.commands.vault.require_persistent_keyring"),
        patch("devops_cli.commands.vault.keyring_write") as write,
    ):
        yield write


def test_login_stores_one_record_bound_to_the_issuing_vault(
    monkeypatch: pytest.MonkeyPatch, usable_keyring: MagicMock
) -> None:
    monkeypatch.setenv("VAULT_NAMESPACE", "team-a")
    with patch(_REQUEST, return_value=reply(200, _LOGIN_REPLY)):
        res = runner.invoke(app, _LOGIN)

    assert (res.exit_code, "s.issued" in res.output) == (0, False)
    key, value = usable_keyring.call_args.args
    record = VaultStoredLogin.model_validate_json(value)
    assert (usable_keyring.call_count, key) == (1, CONST_VAULT_LOGIN_KEYRING_KEY)
    assert (record.token, record.vault_addr, record.namespace) == ("s.issued", VAULT_ADDR, "team-a")


def test_login_fails_when_the_keyring_refuses_the_token(usable_keyring: MagicMock) -> None:
    usable_keyring.side_effect = KeyringLockedError("Cannot store vault_token: locked")
    with patch(_REQUEST, return_value=reply(200, _LOGIN_REPLY)):
        res = runner.invoke(app, _LOGIN)
    assert (res.exit_code, "could not keep the Vault token" in res.output) == (1, True)


def test_login_without_a_persistent_keyring_exits_before_logging_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Under DEVOPS_CLI_HEADLESS_AUTH the token would be lost, so no login request is made."""
    monkeypatch.setenv("DEVOPS_CLI_HEADLESS_AUTH", "1")
    with patch(_REQUEST) as mock_request:
        res = runner.invoke(app, _LOGIN)

    assert res.exit_code == 1
    assert all(text in res.output for text in ("--no-store", "VAULT_TOKEN", "CI runners"))
    mock_request.assert_not_called()


def test_login_with_no_store_checks_credentials_and_keeps_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_HEADLESS_AUTH", "1")
    with (
        patch(_REQUEST, return_value=reply(200, _LOGIN_REPLY)),
        patch("devops_cli.commands.vault.keyring_write") as write,
    ):
        res = runner.invoke(app, [*_LOGIN, "--no-store"])

    assert (res.exit_code, "did not keep the token" in res.output) == (0, True)
    write.assert_not_called()
    assert get_keyring_secret(CONST_VAULT_LOGIN_KEYRING_KEY) is None


def test_login_refused_by_vault_exits_1(usable_keyring: MagicMock) -> None:
    with patch(_REQUEST, return_value=reply(400)):
        res = runner.invoke(app, _LOGIN)
    assert (res.exit_code, "status 400" in res.output) == (1, True)
    usable_keyring.assert_not_called()


def test_login_rejects_an_unknown_method() -> None:
    res = runner.invoke(app, ["login", "--method", "ldap"])
    assert (res.exit_code, "Unsupported Vault auth method" in res.output) == (1, True)


def test_login_and_kubernetes_help_name_the_no_store_form() -> None:
    res = runner.invoke(app, ["login", "--help"], env={"COLUMNS": "250"})
    assert res.output.count("--no-store") >= 2


# ─────────────────────────────────────────────────────────────────────────────
# vault logout
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def stored_entry() -> Iterator[dict[str, Any]]:
    """An unlocked keyring holding one entry, with reads and deletes recorded."""
    entry: dict[str, Any] = {"value": _record(), "delete": MagicMock(return_value=True)}
    with (
        patch("devops_cli.commands.vault.require_persistent_keyring"),
        patch("devops_cli.commands.vault.keyring_read", side_effect=lambda key: entry["value"]),
        patch("devops_cli.commands.vault.keyring_delete", entry["delete"]),
    ):
        yield entry


def test_logout_revokes_at_the_stored_address_then_deletes(
    monkeypatch: pytest.MonkeyPatch, stored_entry: dict[str, Any]
) -> None:
    monkeypatch.setenv("VAULT_ADDR", "https://example.com:9999")
    with patch(_REQUEST, return_value=httpx2.Response(204)) as mock_request:
        res = runner.invoke(app, ["logout"])

    call = mock_request.call_args
    assert res.exit_code == 0
    assert (call.args, call.kwargs["headers"]["X-Vault-Token"]) == (
        ("POST", f"{VAULT_ADDR}/v1/auth/token/revoke-self"),
        STORED_TOKEN,
    )
    stored_entry["delete"].assert_called_once_with(CONST_VAULT_LOGIN_KEYRING_KEY)


def test_logout_deletes_the_local_copy_when_vault_is_unreachable(
    stored_entry: dict[str, Any],
) -> None:
    with patch(_REQUEST, side_effect=httpx2.ConnectError("refused")):
        res = runner.invoke(app, ["logout"])

    assert (res.exit_code, "did not revoke it" in res.output) == (0, True)
    stored_entry["delete"].assert_called_once_with(CONST_VAULT_LOGIN_KEYRING_KEY)


def test_logout_without_a_stored_token_says_so(stored_entry: dict[str, Any]) -> None:
    stored_entry["value"] = None
    with patch(_REQUEST) as mock_request:
        res = runner.invoke(app, ["logout"])

    assert (res.exit_code, "No Vault token is stored" in res.output) == (0, True)
    mock_request.assert_not_called()
    stored_entry["delete"].assert_not_called()


def test_logout_deletes_a_bare_token_without_sending_it(stored_entry: dict[str, Any]) -> None:
    """An entry that names no Vault is never sent anywhere, but it is removed."""
    stored_entry["value"] = "s.bare-token"
    with patch(_REQUEST) as mock_request:
        res = runner.invoke(app, ["logout"])

    assert (res.exit_code, "did not revoke it" in res.output) == (0, True)
    mock_request.assert_not_called()
    stored_entry["delete"].assert_called_once_with(CONST_VAULT_LOGIN_KEYRING_KEY)


def test_logout_dry_run_sends_and_deletes_nothing(stored_entry: dict[str, Any]) -> None:
    with patch(_REQUEST) as mock_request:
        res = runner.invoke(app, ["logout"], env={"DEVOPS_CLI_DRY_RUN": "true"})

    assert (res.exit_code, f"{VAULT_ADDR}/v1/auth/token/revoke-self" in res.output) == (0, True)
    mock_request.assert_not_called()
    stored_entry["delete"].assert_not_called()


@pytest.mark.parametrize(
    "refusal",
    [
        KeyringUnavailableError("no encrypted OS keyring backend is available"),
        KeyringLockedError("Cannot read keyring-unlock-probe: the OS keyring is locked"),
    ],
)
def test_logout_with_an_unreadable_keyring_exits_1(refusal: Exception) -> None:
    """Without an encrypted, unlocked keyring, logout fails rather than claiming no token."""
    with (
        patch("devops_cli.commands.vault.require_persistent_keyring", side_effect=refusal),
        patch("devops_cli.commands.vault.keyring_delete") as delete,
    ):
        res = runner.invoke(app, ["logout"])

    assert (res.exit_code, "Cannot read the stored Vault token" in res.output) == (1, True)
    delete.assert_not_called()
