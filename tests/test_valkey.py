"""Tests of the Valkey client and the `devops valkey` commands."""

from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import valkey.client
from fakeredis import FakeServer
from typer.testing import CliRunner

from devops_cli.commands.valkey import app
from devops_cli.config.defaults import DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS
from devops_cli.exceptions.valkey import (
    ValkeyAuthenticationError,
    ValkeyCommandError,
    ValkeyConnectionError,
    ValkeyTimeoutError,
)
from devops_cli.valkey.client import ValkeyClient
from tests.support.fakes.valkey import bulk_reply, serving_valkey, valkey_client_on
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

runner = CliRunner()

_PUBLIC_ANSWER = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.10", 6379))
_LINK_LOCAL_ANSWER = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 6379))
_PRIVATE_ANSWER = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 6379))


# =============================================================================
# 1. ValkeyClient: destination check, commands, failures
# =============================================================================


class TestValkeyClientDestination:
    """The egress check refuses unsafe destinations before and at every dial."""

    def test_reject_ssrf_and_invalid_host(self) -> None:
        with pytest.raises(ValkeyConnectionError, match="Invalid or prohibited"):
            ValkeyClient(host="169.254.169.254", port=6379)

    def test_empty_host_rejected(self) -> None:
        with pytest.raises(ValkeyConnectionError, match="host cannot be empty"):
            ValkeyClient(host="")

    def test_private_ip_rejected_when_not_allowed(self) -> None:
        with pytest.raises(ValkeyConnectionError, match="non-public IP disallowed"):
            ValkeyClient(host="10.0.0.1", allow_private_network=False)

    def test_hostname_resolving_to_link_local_rejected(self) -> None:
        with patch("socket.getaddrinfo", return_value=[_LINK_LOCAL_ANSWER]):
            with pytest.raises(
                ValkeyConnectionError, match="link-local metadata endpoints are prohibited"
            ):
                ValkeyClient(host="example.com", port=6379)

    def test_hostname_resolving_to_private_rejected_when_not_allowed(self) -> None:
        with patch("socket.getaddrinfo", return_value=[_PRIVATE_ANSWER]):
            with pytest.raises(ValkeyConnectionError, match="non-public IP disallowed"):
                ValkeyClient(host="example.com", allow_private_network=False)

    def test_hostname_dns_failure_rejected_when_private_not_allowed(self) -> None:
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name or service not known")):
            with pytest.raises(ValkeyConnectionError, match="DNS resolution failed"):
                ValkeyClient(host="example.com", allow_private_network=False)

    def test_hostname_dns_failure_is_left_to_the_dial_when_private_networks_are_allowed(
        self,
    ) -> None:
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name or service not known")):
            client = ValkeyClient(host="example.com")
        assert (client.host, client.port) == ("example.com", 6379)

    def test_a_name_that_resolves_to_link_local_at_dial_time_is_refused_then(self) -> None:
        """The first answer passes construction; the answer at the dial is checked again."""
        answers = iter([[_PUBLIC_ANSWER], [_LINK_LOCAL_ANSWER]])
        with patch("socket.getaddrinfo", side_effect=lambda *args, **kwargs: next(answers)):
            client = ValkeyClient(host="example.com")
            with pytest.raises(
                ValkeyConnectionError, match="link-local metadata endpoints are prohibited"
            ):
                client.ping()

    def test_a_name_that_resolves_to_a_non_public_address_at_dial_time_is_refused_when_private_networks_are_not_allowed(
        self, public_dns: str, refusing_port: int
    ) -> None:
        """The name resolves publicly at construction, then to loopback when the dial resolves it.

        Loopback is non-public, so with private networks disallowed the check itself refuses the
        dial. A client that let the flag lapse would dial `refusing_port` and fail with the
        kernel's refusal instead.
        """
        client = ValkeyClient(host="example.com", port=refusing_port, allow_private_network=False)
        loopback = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", refusing_port))
        with patch("socket.getaddrinfo", return_value=[loopback]):
            with pytest.raises(ValkeyConnectionError, match="non-public IP disallowed"):
                client.ping()


class TestValkeyClientCommands:
    """The commands devops-cli sends, against an in-memory server."""

    def test_a_value_is_set_and_read(self, valkey_client: ValkeyClient) -> None:
        assert (
            valkey_client.get("session"),
            valkey_client.set("session", "token"),
            valkey_client.get("session"),
        ) == (None, True, "token")

    def test_a_value_set_with_an_expiry_carries_that_lifetime(
        self, valkey_client: ValkeyClient
    ) -> None:
        valkey_client.set("session", "token", ex=60)
        assert 0 < valkey_client.execute("TTL", "session") <= 60

    def test_keys_are_listed_counted_and_flushed(self, valkey_client: ValkeyClient) -> None:
        for name in ("run:1", "run:2", "other"):
            valkey_client.set(name, "x")
        assert (
            sorted(valkey_client.keys("run:*")),
            valkey_client.dbsize(),
            valkey_client.flushdb(),
            valkey_client.dbsize(),
        ) == (["run:1", "run:2"], 3, True, 0)

    def test_flushall_empties_every_database(self, valkey_client: ValkeyClient) -> None:
        valkey_client.set("a", "1")
        assert (valkey_client.flushall(), valkey_client.dbsize()) == (True, 0)

    def test_execute_returns_each_reply_as_the_server_sent_it(
        self, valkey_client: ValkeyClient
    ) -> None:
        assert [
            valkey_client.execute("PING"),
            valkey_client.execute("SET", "a", "b"),
            valkey_client.execute("GET", "missing"),
            valkey_client.execute("ZADD", "scores", 1.5, "m"),
            valkey_client.execute("ZRANGE", "scores", 0, -1),
        ] == ["PONG", "OK", None, 1, ["m"]]

    def test_ping_reports_a_live_server(self, valkey_client: ValkeyClient) -> None:
        assert valkey_client.ping() is True

    def test_a_snapshot_is_acknowledged(self, valkey_client: ValkeyClient) -> None:
        assert valkey_client.bgsave() == "Background saving started"

    def test_info_is_parsed_into_a_dict(self) -> None:
        text = "# Server\r\nvalkey_version:8.0.0\r\nuptime_in_seconds:3600\r\n"
        with serving_valkey({"INFO": bulk_reply(text.encode())}) as (port, _received):
            client = ValkeyClient(host="127.0.0.1", port=port)
            info = client.info()
            client.close()
        assert info == {"valkey_version": "8.0.0", "uptime_in_seconds": 3600}

    def test_a_pipeline_returns_one_reply_per_command_in_order(
        self, valkey_client: ValkeyClient
    ) -> None:
        replies = valkey_client.pipeline(
            [["SET", "x", "1"], ["ZADD", "scores", 1.5, "m"], ["GET", "x"]]
        )
        assert replies == ["OK", 1, "1"]

    def test_an_empty_pipeline_sends_nothing(self, valkey_client: ValkeyClient) -> None:
        assert valkey_client.pipeline([]) == []

    def test_a_long_pipeline_goes_out_in_bounded_batches(
        self, valkey_client: ValkeyClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No batch holds more than the chunk size, so a mass write cannot buffer without bound."""
        sent: list[int] = []
        execute = valkey.client.Pipeline.execute

        def recording_execute(self: valkey.client.Pipeline, raise_on_error: bool = True) -> Any:
            sent.append(len(self.command_stack))
            return execute(self, raise_on_error)

        monkeypatch.setattr(valkey.client.Pipeline, "execute", recording_execute)
        total = DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS * 2 + 5
        replies = valkey_client.pipeline([["SET", f"key-{n}", n] for n in range(total)])
        assert (sent, len(replies), valkey_client.dbsize()) == (
            [DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS] * 2 + [5],
            total,
            total,
        )

    def test_threads_share_one_client_and_each_reads_its_own_values(
        self, valkey_client: ValkeyClient
    ) -> None:
        """A reply is matched to the thread that asked, never read by another."""

        def round_trips(worker: int) -> list[tuple[str | None, str]]:
            mismatches = []
            for step in range(50):
                key, value = f"key-{worker}-{step}", f"value-{worker}-{step}"
                valkey_client.set(key, value)
                if (read := valkey_client.get(key)) != value:
                    mismatches.append((read, value))
            return mismatches

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(round_trips, range(8), timeout=THREAD_HANDOFF_BOUND_SECONDS))
        assert results == [[]] * 8


class TestValkeyClientConnection:
    """What the client's own arguments make a new connection send and read, over a loopback socket.

    These tests reach the pool the client builds from its arguments. The in-memory server of the
    other classes connects through the `connection_pool` seam with a pool of its own, so it
    cannot show that the client passes its password, database or decoding settings on.
    """

    @pytest.mark.parametrize(
        ("arguments", "announced"),
        [
            pytest.param({}, [], id="neither"),
            pytest.param({"password": "s3cret"}, [["AUTH", "s3cret"]], id="password"),
            pytest.param({"db": 3}, [["SELECT", "3"]], id="database"),
            pytest.param(
                {"password": "s3cret", "db": 3},
                [["AUTH", "s3cret"], ["SELECT", "3"]],
                id="password-and-database",
            ),
        ],
    )
    def test_a_new_connection_authenticates_and_selects_what_the_client_was_given(
        self, arguments: dict[str, Any], announced: list[list[str]]
    ) -> None:
        with serving_valkey({"PING": b"+PONG\r\n"}) as (port, received):
            client = ValkeyClient(host="127.0.0.1", port=port, **arguments)
            pinged = client.ping()
            client.close()
        assert (pinged, received) == (True, [*announced, ["PING"]])

    def test_a_reply_that_is_not_utf8_is_decoded_with_replacement(self) -> None:
        with serving_valkey({"GET": bulk_reply(b"ok\xff")}) as (port, _received):
            client = ValkeyClient(host="127.0.0.1", port=port)
            values = (client.get("blob"), client.execute("GET", "blob"))
            client.close()
        assert values == ("ok\ufffd", "ok\ufffd")


class TestValkeyClientFailures:
    """Every failure arrives as the matching `ValkeyError`, never as a valkey-py exception."""

    def test_a_wrong_password_is_an_authentication_error(self) -> None:
        server = FakeServer(server_type="valkey", config={b"requirepass": b"correct"})
        client = valkey_client_on(server, password="wrong")
        with pytest.raises(ValkeyAuthenticationError, match="Authentication failed"):
            client.ping()

    def test_the_right_password_connects(self) -> None:
        server = FakeServer(server_type="valkey", config={b"requirepass": b"correct"})
        assert valkey_client_on(server, password="correct").ping() is True

    def test_a_command_the_server_rejects_is_a_command_error(
        self, valkey_client: ValkeyClient
    ) -> None:
        with pytest.raises(ValkeyCommandError, match="unknown command"):
            valkey_client.execute("NOSUCHCOMMAND")

    def test_a_rejected_command_in_a_pipeline_is_a_command_error(
        self, valkey_client: ValkeyClient
    ) -> None:
        with pytest.raises(ValkeyCommandError, match="wrong number of arguments"):
            valkey_client.pipeline([["SET", "x", "1"], ["SET", "x"]])

    def test_a_dropped_server_is_a_connection_error_for_every_kind_of_call(
        self, valkey_server: FakeServer, valkey_client: ValkeyClient
    ) -> None:
        valkey_server.connected = False
        for call in (
            valkey_client.ping,
            lambda: valkey_client.execute("GET", "k"),
            lambda: valkey_client.pipeline([["GET", "k"]]),
            lambda: valkey_client.keys("*"),
        ):
            with pytest.raises(ValkeyConnectionError, match="Failed to connect to Valkey"):
                call()

    def test_a_refused_port_is_a_connection_error_naming_the_endpoint(
        self, refusing_port: int
    ) -> None:
        client = ValkeyClient(host="127.0.0.1", port=refusing_port)
        with pytest.raises(ValkeyConnectionError) as raised:
            client.ping()
        assert raised.value.details == {"host": "127.0.0.1", "port": refusing_port}

    def test_a_silent_server_is_a_timeout_error(self, prevent_external_network_calls: None) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            client = ValkeyClient(host="127.0.0.1", port=port, timeout=0.05)
            with pytest.raises(ValkeyTimeoutError) as raised:
                client.ping()
        assert raised.value.details == {"host": "127.0.0.1", "port": port, "timeout_seconds": 0.05}


# =============================================================================
# 2. CLI Command Tests
# =============================================================================


class TestValkeyCliCommands:
    """Tests for devops valkey CLI commands."""

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_ping_success(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["ping"])
        assert res.exit_code == 0
        assert "PONG" in res.output

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_ping_failure(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.ping.side_effect = ValkeyConnectionError("Connection refused")
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["ping"])
        assert res.exit_code != 0
        assert "Valkey ping failed" in res.output

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_info(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.info.return_value = {"valkey_version": "8.0.0", "connected_clients": "1"}
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["info", "--section", "server"])
        assert res.exit_code == 0
        assert "valkey_version" in res.output

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_stats(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.info.return_value = {
            "valkey_version": "8.0.0",
            "uptime_in_seconds": 3600,
            "connected_clients": 2,
            "used_memory_human": "5M",
            "used_memory_peak_human": "6M",
            "total_connections_received": 100,
            "total_commands_processed": 500,
        }
        mock_client.dbsize.return_value = 15
        mock_client.host = "127.0.0.1"
        mock_client.port = 6379
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["stats"])
        assert res.exit_code == 0
        assert "Valkey Server Diagnostic Statistics" in res.output
        assert "15" in res.output

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_keys(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.keys.return_value = ["session:1", "session:2"]
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["keys", "session:*"])
        assert res.exit_code == 0
        assert "session:1" in res.output
        assert "session:2" in res.output

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_keys_empty(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.keys.return_value = []
        mock_client.db = 0
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["keys", "nonexistent*"])
        assert res.exit_code == 0
        assert "No keys matching" in res.output

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_get(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.get.return_value = "hello-world"
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["get", "greeting"])
        assert res.exit_code == 0
        assert "hello-world" in res.output

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_get_not_found(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["get", "missing"])
        assert res.exit_code == 0
        assert "not found" in res.output

    def test_cli_set_stores_the_value_with_its_expiry(self, valkey_client: ValkeyClient) -> None:
        with patch("devops_cli.commands.valkey._resolve_client", return_value=valkey_client):
            res = runner.invoke(app, ["set", "k", "v", "--ex", "30"])
        assert (res.exit_code, "Set 'k' successfully (TTL: 30s)." in res.output) == (0, True)
        assert (valkey_client.get("k"), 0 < valkey_client.execute("TTL", "k") <= 30) == ("v", True)

    def test_cli_set_dry_run(self) -> None:
        res = runner.invoke(app, ["set", "k", "v", "--dry-run"])
        assert res.exit_code == 0
        assert "DRY_RUN" in res.output

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_flush(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.db = 0
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["flush"])
        assert res.exit_code == 0
        assert "Flushed Valkey database 0" in res.output

    def test_cli_flush_dry_run(self) -> None:
        res = runner.invoke(app, ["flush", "--dry-run"])
        assert res.exit_code == 0
        assert "DRY_RUN" in res.output

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_backup(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.bgsave.return_value = "Background saving started"
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["backup"])
        assert res.exit_code == 0
        assert "Backup initiated" in res.output

    def test_cli_backup_dry_run(self) -> None:
        res = runner.invoke(app, ["backup", "--dry-run"])
        assert res.exit_code == 0
        assert "DRY_RUN" in res.output

    def test_cli_raw_execution_prints_replies_as_the_server_sent_them(
        self, valkey_client: ValkeyClient
    ) -> None:
        with patch("devops_cli.commands.valkey._resolve_client", return_value=valkey_client):
            outputs = [
                runner.invoke(app, ["cli", *command]).output
                for command in (
                    ["PING"],
                    ["SET", "greeting", "hello"],
                    ["RPUSH", "mylist", "item1", "item2"],
                    ["LRANGE", "mylist", "0", "1"],
                )
            ]
        assert outputs == ["PONG\n", "OK\n", "2\n", "item1\nitem2\n"]

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_error_masks_credentials(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        from devops_cli.exceptions.valkey import ValkeyError

        mock_client.ping.side_effect = ValkeyError(
            "Connection failed with token=ghp_secretvalkey12345678901234567890123456"
        )
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["ping"])
        assert res.exit_code != 0
        assert "ghp_secretvalkey" not in res.output
        assert "<masked-github-token>" in res.output


def test_parse_valkey_endpoint_formats() -> None:
    """Ensure parse_valkey_endpoint handles hostname:port, raw host, and uri schemes."""
    from devops_cli.valkey.client import parse_valkey_endpoint

    assert parse_valkey_endpoint("localhost:6379") == ("localhost", 6379)
    assert parse_valkey_endpoint("127.0.0.1:6380") == ("127.0.0.1", 6380)
    assert parse_valkey_endpoint("localhost", default_port=6379) == ("localhost", 6379)
    assert parse_valkey_endpoint("valkey://localhost:6379") == ("localhost", 6379)
    assert parse_valkey_endpoint("redis://127.0.0.1:6379") == ("127.0.0.1", 6379)
    assert parse_valkey_endpoint("[::1]:6379") == ("::1", 6379)
    assert parse_valkey_endpoint("[::1]") == ("::1", 6379)
    assert parse_valkey_endpoint("[2001:db8::1]:6379") == ("2001:db8::1", 6379)
    assert parse_valkey_endpoint("valkey://[2001:db8::1]") == ("2001:db8::1", 6379)
    assert parse_valkey_endpoint("valkey://[2001:db8::1]:6382") == ("2001:db8::1", 6382)
    assert parse_valkey_endpoint("VALKEY://[2001:db8::1]:6381") == ("2001:db8::1", 6381)
    assert parse_valkey_endpoint("REDIS://localhost:6379") == ("localhost", 6379)
    assert parse_valkey_endpoint("TCP://127.0.0.1:6379") == ("127.0.0.1", 6379)


def test_valkey_config_hostname_port_normalization() -> None:
    """Ensure ValkeyConfig normalizes host and port into standard hostname:port."""
    from devops_cli.config.settings import ValkeyConfig

    cfg1 = ValkeyConfig(host="localhost:6379")
    assert cfg1.host == "localhost:6379"
    assert cfg1.port == 6379

    cfg2 = ValkeyConfig(host="localhost", port=6380)
    assert cfg2.host == "localhost:6380"
    assert cfg2.port == 6380

    cfg3 = ValkeyConfig(host="[2001:db8::1]:6379")
    assert cfg3.host == "[2001:db8::1]:6379"
    assert cfg3.port == 6379

    cfg4 = ValkeyConfig(host="valkey://[2001:db8::1]:6382")
    assert cfg4.host == "[2001:db8::1]:6382"
    assert cfg4.port == 6382

    cfg5 = ValkeyConfig(host="VALKEY://[2001:db8::1]:6383")
    assert cfg5.host == "[2001:db8::1]:6383"
    assert cfg5.port == 6383


def test_valkey_cli_error_and_edge_cases() -> None:
    """Verify error handlers and edge cases across Valkey CLI commands."""
    from devops_cli.exceptions.valkey import ValkeyError

    # 1. Ping returning False
    with patch("devops_cli.commands.valkey._resolve_client") as mock_res:
        mock_client = MagicMock()
        mock_client.ping.return_value = False
        mock_res.return_value = mock_client
        res = runner.invoke(app, ["ping"])
        assert res.exit_code == 0
        assert "Server responded without PONG acknowledgment" in res.output

    # 2. Info raising ValkeyError
    with patch("devops_cli.commands.valkey._resolve_client") as mock_res:
        mock_client = MagicMock()
        mock_client.info.side_effect = ValkeyError("info failure", details={"code": 500})
        mock_res.return_value = mock_client
        res = runner.invoke(app, ["info"])
        assert res.exit_code != 0
        assert "Valkey info retrieval failed" in res.output

    # 3. Stats raising ValkeyError
    with patch("devops_cli.commands.valkey._resolve_client") as mock_res:
        mock_client = MagicMock()
        mock_client.info.side_effect = ValkeyError("stats failure", details={"cause": "err"})
        mock_res.return_value = mock_client
        res = runner.invoke(app, ["stats"])
        assert res.exit_code != 0
        assert "Failed collecting Valkey statistics" in res.output

    # 4. Get raising ValkeyError
    with patch("devops_cli.commands.valkey._resolve_client") as mock_res:
        mock_client = MagicMock()
        mock_client.get.side_effect = ValkeyError("get failure")
        mock_res.return_value = mock_client
        res = runner.invoke(app, ["get", "mykey"])
        assert res.exit_code != 0
        assert "Failed to get key" in res.output

    # 5. Set raising ValkeyError
    with patch("devops_cli.commands.valkey._resolve_client") as mock_res:
        mock_client = MagicMock()
        mock_client.set.side_effect = ValkeyError("set failure")
        mock_res.return_value = mock_client
        res = runner.invoke(app, ["set", "mykey", "myval"])
        assert res.exit_code != 0
        assert "Failed to set key" in res.output

    # 6. Flush raising ValkeyError
    with patch("devops_cli.commands.valkey._resolve_client") as mock_res:
        mock_client = MagicMock()
        mock_client.flushdb.side_effect = ValkeyError("flush failure")
        mock_res.return_value = mock_client
        res = runner.invoke(app, ["flush"])
        assert res.exit_code != 0
        assert "Valkey flush failed" in res.output

    # 7. Backup raising ValkeyError
    with patch("devops_cli.commands.valkey._resolve_client") as mock_res:
        mock_client = MagicMock()
        mock_client.bgsave.side_effect = ValkeyError("backup failure")
        mock_res.return_value = mock_client
        res = runner.invoke(app, ["backup"])
        assert res.exit_code != 0
        assert "Failed to initiate Valkey backup" in res.output


def test_ai_runs_connect_brackets_ipv6_host(
    monkeypatch: pytest.MonkeyPatch, mock_keyring: None
) -> None:
    """Verify devops ai runs connect brackets IPv6 host in the Valkey index URL."""
    from devops_cli.commands.ai_runs import app as ai_runs_app

    monkeypatch.setattr(
        "devops_cli.commands.ai_runs.node_port_address",
        lambda *args, **kwargs: ("2001:db8::1", 30379),
    )
    monkeypatch.setattr(
        "devops_cli.commands.ai_runs.secret_value",
        lambda *args, **kwargs: "dummy-pass",
    )
    connected_urls: list[str] = []

    class MockRunIndex:
        @classmethod
        def connect(cls, url: str, password: str) -> MagicMock:
            connected_urls.append(url)
            mock = MagicMock()
            mock.__enter__.return_value = mock
            mock.__exit__.return_value = None
            mock.put.return_value = 0
            return mock

    monkeypatch.setattr("devops_cli.commands.ai_runs.RunIndex", MockRunIndex)
    monkeypatch.setattr("devops_cli.commands.ai_runs.load_runs", lambda: [])
    monkeypatch.setattr("devops_cli.config.settings.save_settings", lambda *args, **kwargs: None)

    res = runner.invoke(ai_runs_app, ["connect"])
    assert res.exit_code == 0
    assert connected_urls == ["valkey://[2001:db8::1]:30379"]
