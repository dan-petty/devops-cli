"""Tests of the Valkey client and the `devops valkey` commands."""

from __future__ import annotations

import socket
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import valkey.client
from fakeredis import FakeServer
from typer.testing import CliRunner

from devops_cli.commands.valkey import app
from devops_cli.config.defaults import DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS
from devops_cli.config.settings import ValkeyConfig, load_settings
from devops_cli.exceptions.valkey import (
    ValkeyAuthenticationError,
    ValkeyCommandError,
    ValkeyConnectionError,
    ValkeyTimeoutError,
)
from devops_cli.valkey.client import ValkeyClient
from tests.support.certificates import LocalCa
from tests.support.fakes.valkey import bulk_reply, serving_valkey, valkey_client_on
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS
from tests.web_fakes import PUBLIC_ADDRESS, scripted_resolver

runner = CliRunner()

# =============================================================================
# 1. ValkeyClient: destination check, commands, failures
# =============================================================================


class TestValkeyClientDestination:
    """The client resolves its host once, when it dials, vets every answer and dials a vetted address.

    The resolver is the shared `ScriptedResolver`, whose answers for a name can change from one
    lookup to the next, as the answers of a rebinding DNS server do. The floor fails a test whose
    code connects to an address that is not loopback, so a refusal that a test expects opens no
    connection.
    """

    def test_empty_host_rejected(self) -> None:
        with pytest.raises(ValkeyConnectionError, match="host cannot be empty"):
            ValkeyClient(host="")

    def test_the_constructor_makes_no_lookup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resolver = scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})
        client = ValkeyClient(host="example.com")
        assert ((client.host, client.port), resolver.lookups) == (
            ("example.com", 6379),
            {"example.com": 0},
        )

    def test_one_dial_makes_one_lookup_and_dials_the_address_it_vetted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The name answers loopback first and a public address after; the client dials loopback."""
        with serving_valkey({"PING": b"+PONG\r\n"}) as (port, received):
            resolver = scripted_resolver(
                monkeypatch, {"example.com": [["127.0.0.1"], [PUBLIC_ADDRESS]]}
            )
            client = ValkeyClient(host="example.com", port=port)
            pinged = client.ping()
            client.close()
        assert (pinged, resolver.lookups, received) == (True, {"example.com": 1}, [["PING"]])

    def test_the_client_dials_the_vetted_addresses_in_answer_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing listens at the first answer, so it refuses the connection; the second accepts it."""
        with serving_valkey({"PING": b"+PONG\r\n"}) as (port, received):
            resolver = scripted_resolver(monkeypatch, {"example.com": [["127.0.0.2", "127.0.0.1"]]})
            client = ValkeyClient(host="example.com", port=port)
            pinged = client.ping()
            client.close()
        assert (pinged, resolver.lookups, received) == (True, {"example.com": 1}, [["PING"]])

    @pytest.mark.parametrize(
        "host", ["example.com", "169.254.169.254", "2852039166", "::ffff:169.254.169.254"]
    )
    def test_a_host_that_answers_cloud_metadata_is_a_connection_error_with_no_dial(
        self, host: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted_resolver(monkeypatch, {"example.com": [["169.254.169.254"]]})
        client = ValkeyClient(host=host, port=6379)
        with pytest.raises(ValkeyConnectionError) as raised:
            client.ping()
        assert (raised.value.message, raised.value.details) == (
            f"The egress check refuses Valkey at {host}:6379: the destination is a cloud metadata address.",
            {"host": host, "port": 6379},
        )

    @pytest.mark.unreachable("example.com")
    def test_a_failed_lookup_is_a_connection_error_that_names_the_host(self) -> None:
        client = ValkeyClient(host="example.com", port=6379)
        with pytest.raises(
            ValkeyConnectionError, match=r"Cannot resolve the Valkey host example\.com: "
        ) as raised:
            client.ping()
        assert raised.value.details == {"host": "example.com", "port": 6379}

    @pytest.mark.unreachable("169.254.1.2:6379")
    def test_a_link_local_address_that_is_not_cloud_metadata_is_dialled(self) -> None:
        """Rootless Podman reaches its host at 169.254.1.2. The floor refuses the connect and names it."""
        client = ValkeyClient(host="169.254.1.2", port=6379)
        with pytest.raises(
            RuntimeError, match=r"edge reached without a fake: 169\.254\.1\.2:6379 "
        ):
            client.ping()

    def test_a_numeric_spelling_is_dialled_as_the_address_it_spells(self) -> None:
        """`2130706433` is 127.0.0.1 to the resolver; the metadata case above judges such a spelling."""
        with serving_valkey({"PING": b"+PONG\r\n"}) as (port, received):
            client = ValkeyClient(host="2130706433", port=port)
            pinged = client.ping()
            client.close()
        assert (pinged, received) == (True, [["PING"]])


class TestValkeyClientTls:
    """A `valkeys://` client dials the vetted address and checks the certificate against the URL host.

    The server is a loopback listener with a certificate from a CA made for the test, which the
    client trusts through `SSL_CERT_FILE`, as it trusts the platform store.
    """

    def test_a_certificate_for_the_url_host_is_accepted(
        self, monkeypatch: pytest.MonkeyPatch, local_ca: LocalCa
    ) -> None:
        resolver = scripted_resolver(monkeypatch, {"example.com": [["127.0.0.1"]]})
        tls = local_ca.server_context("example.com")
        with serving_valkey({"PING": b"+PONG\r\n"}, tls=tls) as (port, received):
            client = ValkeyClient(host=f"valkeys://example.com:{port}")
            pinged = client.ping()
            client.close()
        assert (pinged, resolver.lookups, received) == (True, {"example.com": 1}, [["PING"]])

    def test_a_certificate_for_another_name_is_refused_before_a_command(
        self, monkeypatch: pytest.MonkeyPatch, local_ca: LocalCa
    ) -> None:
        scripted_resolver(monkeypatch, {"example.com": [["127.0.0.1"]]})
        tls = local_ca.server_context("example.org")
        with serving_valkey({"PING": b"+PONG\r\n"}, tls=tls) as (port, received):
            client = ValkeyClient(host=f"valkeys://example.com:{port}")
            with pytest.raises(
                ValkeyConnectionError, match=r"certificate is not valid for 'example\.com'"
            ):
                client.ping()
            client.close()
        assert received == []


# What every save of the settings writes for `valkey.host` and `valkey.port`, the defaults.
_SAVED_VALKEY_ADDRESS = {"host": "localhost:6379", "port": 6379}


@pytest.mark.usefixtures("mock_keyring")
class TestValkeyUrl:
    """`valkey.url` names the endpoint that a Valkey client dials, and its scheme decides TLS.

    A save of the settings writes the default `valkey.host` and `valkey.port`, so each case saves
    them beside the URL. The resolver answers `example.com` with loopback. The server has a
    certificate from a CA made for the test, which the client trusts through `SSL_CERT_FILE`.
    """

    @pytest.mark.parametrize("scheme", ["valkeys", "rediss"])
    def test_a_tls_url_connects_over_tls_to_its_host(
        self,
        scheme: str,
        cli: Callable[..., Any],
        config: Callable[..., Path],
        monkeypatch: pytest.MonkeyPatch,
        local_ca: LocalCa,
    ) -> None:
        resolver = scripted_resolver(monkeypatch, {"example.com": [["127.0.0.1"]]})
        tls = local_ca.server_context("example.com")
        with serving_valkey({"PING": b"+PONG\r\n"}, tls=tls) as (port, received):
            config(valkey={**_SAVED_VALKEY_ADDRESS, "url": f"{scheme}://example.com:{port}"})
            result = cli("valkey", "ping")
        assert (result.exit_code, resolver.lookups, received) == (
            0,
            {"example.com": 1},
            [["PING"]],
        )

    def test_a_tls_url_refuses_a_certificate_for_another_name_before_a_command(
        self,
        cli: Callable[..., Any],
        config: Callable[..., Path],
        monkeypatch: pytest.MonkeyPatch,
        local_ca: LocalCa,
    ) -> None:
        scripted_resolver(monkeypatch, {"example.com": [["127.0.0.1"]]})
        tls = local_ca.server_context("example.org")
        with serving_valkey({"PING": b"+PONG\r\n"}, tls=tls) as (port, received):
            config(valkey={**_SAVED_VALKEY_ADDRESS, "url": f"valkeys://example.com:{port}"})
            result = cli("valkey", "ping")
        assert (result.exit_code, received) == (1, [])
        assert "certificate is not valid for 'example.com'" in result.output

    def test_a_valkey_url_connects_in_plaintext_to_its_host(
        self, cli: Callable[..., Any], config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolver = scripted_resolver(monkeypatch, {"example.com": [["127.0.0.1"]]})
        with serving_valkey({"PING": b"+PONG\r\n"}) as (port, received):
            config(valkey={**_SAVED_VALKEY_ADDRESS, "url": f"valkey://example.com:{port}"})
            result = cli("valkey", "ping")
        assert (result.exit_code, resolver.lookups, received) == (
            0,
            {"example.com": 1},
            [["PING"]],
        )

    @pytest.mark.parametrize(
        ("saved", "endpoint"),
        [
            pytest.param(
                {"url": "valkeys://example.com:6380"}, "valkeys://example.com:6380", id="valkeys"
            ),
            pytest.param({"url": "rediss://example.com"}, "rediss://example.com:6379", id="rediss"),
            pytest.param(
                {"url": "valkey://[2001:db8::1]:6379/0"},
                "valkey://[2001:db8::1]:6379",
                id="valkey-ipv6",
            ),
            pytest.param(
                {"url": "valkeys://:<masked-password>@example.com:6380"},
                "valkeys://example.com:6380",
                id="password-stays-out",
            ),
            pytest.param(
                {**_SAVED_VALKEY_ADDRESS, "url": "valkeys://example.com:6380"},
                "valkeys://example.com:6380",
                id="url-over-saved-host",
            ),
            pytest.param({"host": "example.com:6380"}, "example.com:6380", id="host-without-url"),
            pytest.param(
                {"host": "192.0.2.7:30637", "port": 30637, "url": "http://192.0.2.7:30637"},
                "192.0.2.7:30637",
                id="url-without-a-valkey-scheme",
            ),
        ],
    )
    def test_the_endpoint_is_the_address_behind_the_scheme_of_the_url(
        self, saved: dict[str, Any], endpoint: str
    ) -> None:
        assert ValkeyConfig.model_validate(saved).endpoint == endpoint

    @pytest.mark.parametrize(
        ("url", "environment_host", "endpoint"),
        [
            pytest.param(
                "valkeys://example.com:6380",
                "example.org:6381",
                "valkeys://example.org:6381",
                id="the-url-scheme",
            ),
            pytest.param(
                "valkey://example.com:6379",
                "valkeys://example.org:6381",
                "valkeys://example.org:6381",
                id="its-own-scheme",
            ),
        ],
    )
    def test_an_environment_host_replaces_the_host_of_the_url(
        self,
        url: str,
        environment_host: str,
        endpoint: str,
        config: Callable[..., Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config(valkey={"url": url})
        monkeypatch.setenv("DEVOPS_CLI_VALKEY_HOST", environment_host)
        assert load_settings().valkey.endpoint == endpoint


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
