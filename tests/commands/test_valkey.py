"""Tests of the Valkey client and the `devops valkey` commands."""

from __future__ import annotations

import socket
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer.main
import valkey.client
import yaml
from fakeredis import FakeServer
from typer.testing import CliRunner

from devops_cli.ai.run_store import (
    Mechanism,
    RunIndex,
    RunIndexNotConfiguredError,
    new_run,
    save_run,
)
from devops_cli.commands.valkey import app
from devops_cli.config.defaults import DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS
from devops_cli.config.settings import ValkeyConfig, load_settings, save_settings
from devops_cli.exceptions import ConfigurationError
from devops_cli.exceptions.valkey import (
    ValkeyAuthenticationError,
    ValkeyCommandError,
    ValkeyConnectionError,
    ValkeyTimeoutError,
)
from devops_cli.valkey.client import ValkeyClient
from devops_cli.valkey.endpoint import ValkeyEndpoint, parse_valkey_url
from tests.support.certificates import LocalCa
from tests.support.config_writes import written_keys
from tests.support.fakes.valkey import (
    bulk_reply,
    serving_valkey,
    valkey_client_on,
    valkey_endpoint,
)
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

    def test_the_constructor_makes_no_lookup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resolver = scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})
        client = ValkeyClient(valkey_endpoint("valkey://example.com"))
        assert ((client.host, client.port), resolver.lookups) == (
            ("example.com", 6379),
            {"example.com": 0},
        )

    def test_valkey_protocol_is_satisfied_by_valkey_client(
        self, valkey_client: ValkeyClient, keyring_store: Any
    ) -> None:
        from devops_cli.valkey.client import (
            ValkeyProtocol,
            reset_valkey_client,
            resolve_valkey_client,
        )

        assert isinstance(valkey_client, ValkeyProtocol)
        valkey_client.set("proto_key", "proto_val")
        assert valkey_client.get("proto_key") == "proto_val"
        assert valkey_client.mget(["proto_key"]) == ["proto_val"]
        assert valkey_client.mget() == []
        assert valkey_client.delete("proto_key") == 1
        assert valkey_client.delete() == 0
        assert valkey_client.get("proto_key") is None
        cursor, keys = valkey_client.scan(0)
        assert isinstance(cursor, int)
        assert isinstance(keys, list)
        from devops_cli.exceptions.valkey import ValkeyCommandError

        with pytest.raises(ValkeyCommandError):
            valkey_client.eval("return 42", 0)

        reset_valkey_client()
        try:
            client_url = resolve_valkey_client("valkey://127.0.0.1:6379/1")
            assert client_url.db == 1
            client_default = resolve_valkey_client()
            assert isinstance(client_default.port, int)
        finally:
            reset_valkey_client()

    def test_valkey_fixture(self, valkey: ValkeyClient, keyring_store: Any) -> None:
        from devops_cli.commands.valkey import _resolve_client

        client = _resolve_client()
        assert client is valkey
        assert client.ping() is True

    def test_one_dial_makes_one_lookup_and_dials_the_address_it_vetted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The name answers loopback first and a public address after; the client dials loopback."""
        with serving_valkey({"PING": b"+PONG\r\n"}) as (port, received):
            resolver = scripted_resolver(
                monkeypatch, {"example.com": [["127.0.0.1"], [PUBLIC_ADDRESS]]}
            )
            client = ValkeyClient(valkey_endpoint(f"valkey://example.com:{port}"))
            pinged = client.ping()
            client.close()
        assert (pinged, resolver.lookups, received) == (True, {"example.com": 1}, [["PING"]])

    def test_the_client_dials_the_vetted_addresses_in_answer_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing listens at the first answer, so it refuses the connection; the second accepts it."""
        with serving_valkey({"PING": b"+PONG\r\n"}) as (port, received):
            resolver = scripted_resolver(monkeypatch, {"example.com": [["127.0.0.2", "127.0.0.1"]]})
            client = ValkeyClient(valkey_endpoint(f"valkey://example.com:{port}"))
            pinged = client.ping()
            client.close()
        assert (pinged, resolver.lookups, received) == (True, {"example.com": 1}, [["PING"]])

    @pytest.mark.parametrize(
        ("authority", "host"),
        [
            ("example.com", "example.com"),
            ("169.254.169.254", "169.254.169.254"),
            ("2852039166", "2852039166"),
            # The URL parser writes an IPv6 address in its normal form.
            ("[::ffff:169.254.169.254]", "::ffff:a9fe:a9fe"),
        ],
    )
    def test_a_host_that_answers_cloud_metadata_is_a_connection_error_with_no_dial(
        self, authority: str, host: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted_resolver(monkeypatch, {"example.com": [["169.254.169.254"]]})
        client = ValkeyClient(valkey_endpoint(f"valkey://{authority}:6379"))
        with pytest.raises(ValkeyConnectionError) as raised:
            client.ping()
        assert (raised.value.message, raised.value.details) == (
            f"The egress check refuses Valkey at {host}:6379: the destination is a cloud metadata address.",
            {"host": host, "port": 6379},
        )

    @pytest.mark.unreachable("example.com")
    def test_a_failed_lookup_is_a_connection_error_that_names_the_host(self) -> None:
        client = ValkeyClient(valkey_endpoint("valkey://example.com:6379"))
        with pytest.raises(
            ValkeyConnectionError, match=r"Cannot resolve the Valkey host example\.com: "
        ) as raised:
            client.ping()
        assert raised.value.details == {"host": "example.com", "port": 6379}

    @pytest.mark.unreachable("169.254.1.2:6379")
    def test_a_link_local_address_that_is_not_cloud_metadata_is_dialled(self) -> None:
        """Rootless Podman reaches its host at 169.254.1.2. The floor refuses the connect and names it."""
        client = ValkeyClient(valkey_endpoint("valkey://169.254.1.2:6379"))
        with pytest.raises(
            RuntimeError, match=r"edge reached without a fake: 169\.254\.1\.2:6379 "
        ):
            client.ping()

    def test_a_numeric_spelling_is_dialled_as_the_address_it_spells(self) -> None:
        """`2130706433` is 127.0.0.1 to the resolver; the metadata case above judges such a spelling."""
        with serving_valkey({"PING": b"+PONG\r\n"}) as (port, received):
            client = ValkeyClient(valkey_endpoint(f"valkey://2130706433:{port}"))
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
            client = ValkeyClient(valkey_endpoint(f"valkeys://example.com:{port}"))
            pinged = client.ping()
            client.close()
        assert (pinged, resolver.lookups, received) == (True, {"example.com": 1}, [["PING"]])

    def test_a_certificate_for_another_name_is_refused_before_a_command(
        self, monkeypatch: pytest.MonkeyPatch, local_ca: LocalCa
    ) -> None:
        scripted_resolver(monkeypatch, {"example.com": [["127.0.0.1"]]})
        tls = local_ca.server_context("example.org")
        with serving_valkey({"PING": b"+PONG\r\n"}, tls=tls) as (port, received):
            client = ValkeyClient(valkey_endpoint(f"valkeys://example.com:{port}"))
            with pytest.raises(
                ValkeyConnectionError, match=r"certificate is not valid for 'example\.com'"
            ):
                client.ping()
            client.close()
        assert received == []


# The password of a refused URL; no message may quote it.
_URL_PASSWORD = "s3cret-in-url"

# Each URL that a Valkey setting refuses, and the words of the reason that its message gives.
_REFUSED_URLS = [
    pytest.param("valkey://2001:db8::1:6379", "invalid port number", id="ipv6-without-brackets"),
    pytest.param(
        f"valkey://user:{_URL_PASSWORD}@example.com:6379", "user name or a password", id="userinfo"
    ),
    pytest.param(
        f"valkey://:{_URL_PASSWORD}@example.com:6379", "user name or a password", id="password"
    ),
    pytest.param("valkey://example.com:99999", "invalid port number", id="port-out-of-range"),
    pytest.param("valkey://example.com:abc", "invalid port number", id="port-not-a-number"),
    pytest.param("valkey://example.com:0", "port 0", id="port-0"),
    pytest.param("valkey://example.com:6379/notanint", "database", id="database-not-an-integer"),
    pytest.param("valkey://example.com:6379/-1", "database", id="negative-database"),
    pytest.param("valkey://example.com:6379/1?db=2", "database", id="two-databases"),
    pytest.param("valkey://example.com:6379?ssl=true", "'ssl'", id="unknown-query-key"),
    pytest.param("valkey://example.com:6379#frag", "fragment", id="fragment"),
    pytest.param("redis://example.com:6379", "'redis'", id="redis"),
    pytest.param("rediss://example.com:6379", "'rediss'", id="rediss"),
    pytest.param(f"tcp://:{_URL_PASSWORD}@example.com:6379", "'tcp'", id="tcp"),
    pytest.param("unix:///run/valkey.sock", "'unix'", id="unix"),
    pytest.param("http://example.com:6379", "'http'", id="http"),
    pytest.param("localhost:6380", "'localhost'", id="host-read-as-scheme"),
    pytest.param("//example.com:6379", "no scheme", id="no-scheme"),
    pytest.param("valkey://", "empty host", id="no-host"),
]

# The options that could name a Valkey address on the command line. `-h` is the help option.
_ADDRESS_FLAGS = frozenset({"--url", "--host", "--port", "-p"})


@pytest.mark.usefixtures("keyring_store")
class TestValkeyUrl:
    """One rule validates each Valkey URL: `valkey.url`, `runs.index_url` and the `--url` option.

    The resolver answers `example.com` with loopback. The TLS server has a certificate from a CA
    made for the test, which the client trusts through `SSL_CERT_FILE`.
    """

    @pytest.mark.parametrize(
        ("url", "endpoint"),
        [
            pytest.param(
                "valkey://example.com:6379/0",
                ValkeyEndpoint(scheme="valkey", host="example.com", port=6379, db=0),
                id="host-port-database",
            ),
            pytest.param(
                "valkey://example.com/3",
                ValkeyEndpoint(scheme="valkey", host="example.com", port=6379, db=3),
                id="default-port",
            ),
            pytest.param(
                "valkey://example.com:6379?db=4",
                ValkeyEndpoint(scheme="valkey", host="example.com", port=6379, db=4),
                id="database-query",
            ),
            pytest.param(
                "valkeys://example.com:6380/0",
                ValkeyEndpoint(scheme="valkeys", host="example.com", port=6380, db=0),
                id="tls",
            ),
            pytest.param(
                "valkey://[2001:db8::1]:6379/0",
                ValkeyEndpoint(scheme="valkey", host="2001:db8::1", port=6379, db=0),
                id="ipv6",
            ),
            pytest.param(
                "valkey://bücher.example:6379",
                ValkeyEndpoint(scheme="valkey", host="bücher.example", port=6379, db=0),
                id="non-ascii-host",
            ),
        ],
    )
    @pytest.mark.parametrize("setting", ["valkey.url", "runs.index_url", "--url"])
    def test_a_valid_url_names_the_scheme_host_port_and_database(
        self, url: str, endpoint: ValkeyEndpoint, setting: str
    ) -> None:
        assert (parse_valkey_url(url, setting=setting), endpoint.tls) == (
            endpoint,
            endpoint.scheme == "valkeys",
        )

    @pytest.mark.parametrize(("url", "reason"), _REFUSED_URLS)
    def test_each_setting_refuses_an_invalid_url_with_a_message_that_names_it(
        self, url: str, reason: str, config: Callable[..., Path]
    ) -> None:
        config(valkey={"url": url}, runs={"index_url": url})
        settings = load_settings()
        with pytest.raises(ConfigurationError) as valkey_url:
            _ = settings.valkey.endpoint
        with pytest.raises(RunIndexNotConfiguredError) as index_url:
            RunIndex.from_settings()
        with pytest.raises(ConfigurationError) as option:
            parse_valkey_url(url, setting="--url")
        messages = {
            "valkey.url": valkey_url.value.message,
            "runs.index_url": index_url.value.message,
            "--url": option.value.message,
        }
        assert {
            setting: (
                message.startswith(f"{setting} "),
                reason in message,
                _URL_PASSWORD in message,
            )
            for setting, message in messages.items()
        } == {setting: (True, True, False) for setting in messages}

    @pytest.mark.parametrize(
        "argv",
        [["valkey", "ping"], ["valkey", "ping", "--url", f"tcp://:{_URL_PASSWORD}@example.com"]],
        ids=["setting", "option"],
    )
    def test_a_command_given_an_invalid_url_exits_with_the_message_and_no_traceback(
        self, argv: list[str], cli: Callable[..., Any], config: Callable[..., Path]
    ) -> None:
        config(valkey={"url": f"tcp://:{_URL_PASSWORD}@example.com"})
        result = cli(argv)
        output = " ".join(result.output.split())
        setting = "--url" if "--url" in argv else "valkey.url"
        assert (
            result.exit_code,
            f"{setting} has the scheme 'tcp'" in output,
            _URL_PASSWORD in output,
            "Traceback" in output,
        ) == (1, True, False, False)

    def test_a_saved_url_that_is_refused_names_the_command_that_writes_it(
        self, cli: Callable[..., Any], config: Callable[..., Path]
    ) -> None:
        save_run(new_run(Mechanism.CORPUS_SCORE, setup={}, subject={}, results={}))
        config(valkey={"url": "tcp://example.com:6379"}, runs={"index_url": "tcp://example.com"})
        assert (
            "devops k8s configure-urls" in " ".join(cli("valkey", "ping").output.split()),
            "devops ai runs connect" in " ".join(cli("ai", "runs", "reindex").output.split()),
        ) == (True, True)

    def test_an_invalid_url_does_not_stop_the_settings_from_loading(
        self, config: Callable[..., Path]
    ) -> None:
        config(valkey={"url": "tcp://example.com:6379"})
        settings = load_settings()
        with pytest.raises(ConfigurationError) as raised:
            _ = settings.valkey.endpoint
        assert (raised.value.exit_code, raised.value.error_code, raised.value.details) == (
            1,
            "CONFIGURATION_ERROR",
            {"key": "valkey.url"},
        )

    @pytest.mark.parametrize(
        "saved", [{}, {"url": ""}, {"url": None}], ids=["unset", "empty", "null"]
    )
    def test_an_unset_url_is_the_default_endpoint(self, saved: dict[str, Any]) -> None:
        assert ValkeyConfig.model_validate(saved).endpoint == ValkeyEndpoint(
            scheme="valkey", host="localhost", port=6379, db=0
        )

    def test_an_environment_url_replaces_the_url_of_the_file(
        self, config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config(valkey={"url": "valkey://example.com:6379/1"})
        monkeypatch.setenv("DEVOPS_CLI_VALKEY_URL", "valkeys://example.org:6381/2")
        assert load_settings().valkey.endpoint == ValkeyEndpoint(
            scheme="valkeys", host="example.org", port=6381, db=2
        )

    def test_a_file_with_the_removed_host_port_and_db_keys_loads_and_a_save_keeps_them(
        self, config: Callable[..., Path], isolate_data_dir: Path
    ) -> None:
        """Every save before `valkey.url` became the one address wrote `host`, `port` and `db`.
        The loader ignores them, and a save keeps them, as it keeps every key it does not know."""
        removed = {"host": "localhost:6379", "port": 6379, "db": 0}
        path = config(valkey={**removed, "url": "valkey://example.com:6380/1"})
        settings = load_settings()
        settings.github.default_org = "example-org"
        save_settings(settings)
        assert (
            settings.valkey.endpoint,
            yaml.safe_load(path.read_text(encoding="utf-8"))["valkey"],
            written_keys(isolate_data_dir),
        ) == (
            ValkeyEndpoint(scheme="valkey", host="example.com", port=6380, db=1),
            {**removed, "url": "valkey://example.com:6380/1"},
            [["github.default_org"]],
        )

    def test_the_database_of_the_url_is_selected_on_each_new_connection(
        self, cli: Callable[..., Any], config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolver = scripted_resolver(monkeypatch, {"example.com": [["127.0.0.1"]]})
        with serving_valkey({"PING": b"+PONG\r\n"}) as (port, received):
            config(valkey={"url": f"valkey://example.com:{port}/2"})
            result = cli("valkey", "ping")
        assert (result.exit_code, resolver.lookups, received) == (
            0,
            {"example.com": 1},
            [["SELECT", "2"], ["PING"]],
        )

    def test_the_url_option_replaces_the_saved_url(
        self, cli: Callable[..., Any], config: Callable[..., Path]
    ) -> None:
        config(valkey={"url": "tcp://example.com:6379"})
        with serving_valkey({"PING": b"+PONG\r\n"}) as (port, received):
            result = cli("valkey", "ping", "--url", f"valkey://127.0.0.1:{port}/3")
        assert (result.exit_code, received) == (0, [["SELECT", "3"], ["PING"]])

    def test_a_tls_url_connects_over_tls_to_its_host(
        self,
        cli: Callable[..., Any],
        config: Callable[..., Path],
        monkeypatch: pytest.MonkeyPatch,
        local_ca: LocalCa,
    ) -> None:
        resolver = scripted_resolver(monkeypatch, {"example.com": [["127.0.0.1"]]})
        tls = local_ca.server_context("example.com")
        with serving_valkey({"PING": b"+PONG\r\n"}, tls=tls) as (port, received):
            config(valkey={"url": f"valkeys://example.com:{port}"})
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
            config(valkey={"url": f"valkeys://example.com:{port}"})
            result = cli("valkey", "ping")
        assert (result.exit_code, received) == (1, [])
        assert "certificate is not valid for 'example.com'" in result.output

    def test_a_valkey_url_connects_in_plaintext_to_its_host(
        self, cli: Callable[..., Any], config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolver = scripted_resolver(monkeypatch, {"example.com": [["127.0.0.1"]]})
        with serving_valkey({"PING": b"+PONG\r\n"}) as (port, received):
            config(valkey={"url": f"valkey://example.com:{port}"})
            result = cli("valkey", "ping")
        assert (result.exit_code, resolver.lookups, received) == (
            0,
            {"example.com": 1},
            [["PING"]],
        )

    def test_every_valkey_command_takes_a_url_and_no_host_or_port(self) -> None:
        commands = typer.main.get_group(app).commands
        assert {
            name: sorted(
                flag for param in command.params for flag in param.opts if flag in _ADDRESS_FLAGS
            )
            for name, command in commands.items()
        } == {
            name: ["--url"]
            for name in ("ping", "info", "stats", "keys", "get", "set", "flush", "backup", "cli")
        }


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
            client = ValkeyClient(valkey_endpoint(f"valkey://127.0.0.1:{port}"))
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
    """What the client's endpoint and password make a new connection send and read, over a loopback socket.

    These tests reach the pool the client builds from its endpoint. The in-memory server of the
    other classes connects through the `connection_pool` seam with a pool of its own, so it
    cannot show that the client passes its password, database or decoding settings on.
    """

    @pytest.mark.parametrize(
        ("database", "password", "announced"),
        [
            pytest.param("", None, [], id="neither"),
            pytest.param("", "s3cret", [["AUTH", "s3cret"]], id="password"),
            pytest.param("/3", None, [["SELECT", "3"]], id="database"),
            pytest.param(
                "/3", "s3cret", [["AUTH", "s3cret"], ["SELECT", "3"]], id="password-and-database"
            ),
        ],
    )
    def test_a_new_connection_authenticates_and_selects_what_the_client_was_given(
        self, database: str, password: str | None, announced: list[list[str]]
    ) -> None:
        with serving_valkey({"PING": b"+PONG\r\n"}) as (port, received):
            endpoint = valkey_endpoint(f"valkey://127.0.0.1:{port}{database}")
            client = ValkeyClient(endpoint, password=password)
            pinged = client.ping()
            client.close()
        assert (pinged, received) == (True, [*announced, ["PING"]])

    def test_a_refused_password_is_an_authentication_error_that_does_not_quote_it(self) -> None:
        refusal = b"-WRONGPASS invalid username-password pair or user is disabled.\r\n"
        with serving_valkey({"AUTH": refusal}) as (port, _received):
            client = ValkeyClient(valkey_endpoint(f"valkey://127.0.0.1:{port}"), password="s3cret")
            with pytest.raises(ValkeyAuthenticationError) as raised:
                client.ping()
            client.close()
        assert (raised.value.error_code, "s3cret" in raised.value.message) == (
            "VALKEY_AUTHENTICATION_ERROR",
            False,
        )

    def test_a_reply_that_is_not_utf8_is_decoded_with_replacement(self) -> None:
        with serving_valkey({"GET": bulk_reply(b"ok\xff")}) as (port, _received):
            client = ValkeyClient(valkey_endpoint(f"valkey://127.0.0.1:{port}"))
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
        client = ValkeyClient(valkey_endpoint(f"valkey://127.0.0.1:{refusing_port}"))
        with pytest.raises(ValkeyConnectionError) as raised:
            client.ping()
        assert raised.value.details == {"host": "127.0.0.1", "port": refusing_port}

    def test_a_silent_server_is_a_timeout_error(self, prevent_external_network_calls: None) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            client = ValkeyClient(valkey_endpoint(f"valkey://127.0.0.1:{port}"), timeout=0.05)
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
        assert (res.exit_code, res.output) == (
            ValkeyConnectionError("").exit_code,
            "✗ Connection refused\n",
        )

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

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_flush_all_flushes_every_database(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["flush", "--all"])

        assert (
            res.exit_code,
            res.output,
            mock_client.flushall.call_count,
            mock_client.flushdb.call_count,
        ) == (0, "✓ Flushed all Valkey databases.\n", 1, 0)

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_without_a_command_names_the_server_and_runs_nothing(
        self, mock_resolve: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_client.host = "valkey.example.com"
        mock_client.port = 6379
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["cli"])

        assert (
            res.exit_code,
            "valkey.example.com:6379" in res.output,
            mock_client.execute.called,
        ) == (
            0,
            True,
            False,
        )

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
        assert (res.exit_code, res.output) == (ValkeyError("").exit_code, "✗ info failure\n")

    # 3. Stats raising ValkeyError
    with patch("devops_cli.commands.valkey._resolve_client") as mock_res:
        mock_client = MagicMock()
        mock_client.info.side_effect = ValkeyError("stats failure", details={"cause": "err"})
        mock_res.return_value = mock_client
        res = runner.invoke(app, ["stats"])
        assert (res.exit_code, res.output) == (ValkeyError("").exit_code, "✗ stats failure\n")

    # 4. Get raising ValkeyError
    with patch("devops_cli.commands.valkey._resolve_client") as mock_res:
        mock_client = MagicMock()
        mock_client.get.side_effect = ValkeyError("get failure")
        mock_res.return_value = mock_client
        res = runner.invoke(app, ["get", "mykey"])
        assert (res.exit_code, res.output) == (ValkeyError("").exit_code, "✗ get failure\n")

    # 5. Set raising ValkeyError
    with patch("devops_cli.commands.valkey._resolve_client") as mock_res:
        mock_client = MagicMock()
        mock_client.set.side_effect = ValkeyError("set failure")
        mock_res.return_value = mock_client
        res = runner.invoke(app, ["set", "mykey", "myval"])
        assert (res.exit_code, res.output) == (ValkeyError("").exit_code, "✗ set failure\n")

    # 6. Flush raising ValkeyError
    with patch("devops_cli.commands.valkey._resolve_client") as mock_res:
        mock_client = MagicMock()
        mock_client.flushdb.side_effect = ValkeyError("flush failure")
        mock_res.return_value = mock_client
        res = runner.invoke(app, ["flush"])
        assert (res.exit_code, res.output) == (ValkeyError("").exit_code, "✗ flush failure\n")

    # 7. Backup raising ValkeyError
    with patch("devops_cli.commands.valkey._resolve_client") as mock_res:
        mock_client = MagicMock()
        mock_client.bgsave.side_effect = ValkeyError("backup failure")
        mock_res.return_value = mock_client
        res = runner.invoke(app, ["backup"])
        assert (res.exit_code, res.output) == (ValkeyError("").exit_code, "✗ backup failure\n")


def test_ai_runs_connect_brackets_ipv6_host(
    monkeypatch: pytest.MonkeyPatch, keyring_store: None
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


# =============================================================================
# 3. MCP tools: the server is the configured one, never a URL that the model gives (#2634)
# =============================================================================

VALKEY_TOOL_PARAMETERS: dict[str, list[str]] = {
    "valkey_ping": [],
    "valkey_stats": [],
    "valkey_info": ["section"],
    "valkey_get": ["key"],
    "valkey_set": ["key", "value", "ex", "dry_run"],
    "valkey_flush": ["all_databases", "dry_run"],
}
"""Each Valkey tool and the parameters that it publishes. None of them is a URL."""

VALKEY_TOOL_CALLS: dict[str, tuple[dict[str, object], list[list[str]]]] = {
    "valkey_ping": ({}, [["PING"]]),
    "valkey_stats": ({}, [["INFO"], ["DBSIZE"]]),
    "valkey_info": ({"section": "memory"}, [["INFO", "memory"]]),
    "valkey_get": ({"key": "k"}, [["GET", "k"]]),
    "valkey_set": ({"key": "k", "value": "v"}, [["SET", "k", "v"]]),
    "valkey_flush": ({}, [["FLUSHDB"]]),
}
"""Each Valkey tool, arguments that it accepts, and the commands that it sends to the server."""

_VALKEY_REPLIES = {
    "PING": b"+PONG\r\n",
    "INFO": bulk_reply(b"# Server\r\nvalkey_version:8.0.0\r\nuptime_in_seconds:3600\r\n"),
    "DBSIZE": b":3\r\n",
    "GET": bulk_reply(b"v"),
}
_PASSWORD = "FAKE-2634-value"


async def _call_valkey_tool(tool: str, arguments: dict[str, object]) -> tuple[bool, str]:
    """Call a tool the way an MCP client does: whether the call failed, and its reply."""
    from fastmcp import Client

    from devops_cli.ai.mcp.server import mcp

    async with Client(mcp) as client:
        await client.call_tool("hydrate_tool_domain", {"domain": "valkey"})
        result = await client.call_tool(tool, arguments, raise_on_error=False)
    return bool(result.is_error), "\n".join(getattr(block, "text", "") for block in result.content)


@pytest.mark.usefixtures("keyring_store")
class TestValkeyToolsTakeNoUrlFromTheModel:
    """The MCP Valkey tools dial the server of `valkey.url`, never a URL that the calling model
    gives, so the Valkey password goes only to the configured server (#2634)."""

    async def test_the_tools_publish_no_url_parameter(self) -> None:
        """The schema of each tool holds its own options and no URL."""
        from fastmcp import Client

        from devops_cli.ai.mcp.server import mcp

        async with Client(mcp) as client:
            await client.call_tool("hydrate_tool_domain", {"domain": "valkey"})
            tools = await client.list_tools()

        assert {
            tool.name: list(tool.input_schema["properties"])
            for tool in tools
            if tool.name.startswith("valkey_")
        } == VALKEY_TOOL_PARAMETERS

    @pytest.mark.parametrize("tool", list(VALKEY_TOOL_CALLS))
    async def test_a_url_argument_is_refused_and_opens_no_connection(
        self, monkeypatch: pytest.MonkeyPatch, tool: str
    ) -> None:
        """A call that gives a URL fails, and the server at that URL gets no connection.

        On `origin/main` the server at the URL received `AUTH <password>` and then the command of
        the tool, so `valkey_set` and `valkey_flush` also wrote to it.
        """
        monkeypatch.setenv("DEVOPS_CLI_VALKEY_PASSWORD", _PASSWORD)
        arguments, _commands = VALKEY_TOOL_CALLS[tool]
        with serving_valkey(_VALKEY_REPLIES) as (port, received):
            failed, reply = await _call_valkey_tool(
                tool, {**arguments, "url": f"valkey://127.0.0.1:{port}/0"}
            )

        assert (
            failed,
            "1. Parameter: `url`\n   Kind: HALLUCINATED_PARAM\n" in reply,
            received,
        ) == (True, True, [])

    @pytest.mark.parametrize("tool", list(VALKEY_TOOL_CALLS))
    async def test_each_tool_dials_the_configured_server_with_the_password(
        self, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path], tool: str
    ) -> None:
        """The password still reaches the server that the configuration names."""
        monkeypatch.setenv("DEVOPS_CLI_VALKEY_PASSWORD", _PASSWORD)
        arguments, commands = VALKEY_TOOL_CALLS[tool]
        with serving_valkey(_VALKEY_REPLIES) as (port, received):
            config(valkey={"url": f"valkey://127.0.0.1:{port}"})
            failed, _reply = await _call_valkey_tool(tool, arguments)

        assert (failed, received) == (False, [["AUTH", _PASSWORD], *commands])

    def test_the_url_option_of_a_command_sends_the_password_to_the_host_that_a_person_types(
        self, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Any]
    ) -> None:
        """A person types `--url`, and no model gives it, so the password goes to that host."""
        monkeypatch.setenv("DEVOPS_CLI_VALKEY_PASSWORD", _PASSWORD)
        with serving_valkey(_VALKEY_REPLIES) as (port, received):
            result = cli("valkey", "ping", "--url", f"valkey://127.0.0.1:{port}/3")

        assert (result.exit_code, received) == (
            0,
            [["AUTH", _PASSWORD], ["SELECT", "3"], ["PING"]],
        )
