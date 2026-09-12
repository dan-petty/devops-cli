"""Comprehensive unit test suite for Valkey caching tier, RESP protocol, rate limiter, and CLI."""

from __future__ import annotations

import io
import socket
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.cache.valkey_cache import ValkeyCacheProvider
from devops_cli.commands.valkey import app
from devops_cli.exceptions.valkey import (
    ValkeyAuthenticationError,
    ValkeyCommandError,
    ValkeyConnectionError,
    ValkeyTimeoutError,
)
from devops_cli.valkey.client import ValkeyClient, parse_info_response
from devops_cli.valkey.protocol import encode_command, parse_resp
from devops_cli.valkey.rate_limiter import ValkeyTokenBucketRateLimiter

runner = CliRunner()


# =============================================================================
# 1. RESP Protocol Encoding & Parsing Tests
# =============================================================================


class TestRespProtocol:
    """Tests for pure-Python RESP2/RESP3 encoder and stream parser."""

    def test_encode_command_basic(self) -> None:
        encoded = encode_command("PING")
        assert encoded == b"*1\r\n$4\r\nPING\r\n"

    def test_encode_command_with_mixed_arguments(self) -> None:
        encoded = encode_command("SET", "mykey", 42, 3.14, True, b"bytesval")
        expected = (
            b"*6\r\n"
            b"$3\r\nSET\r\n"
            b"$5\r\nmykey\r\n"
            b"$2\r\n42\r\n"
            b"$4\r\n3.14\r\n"
            b"$4\r\ntrue\r\n"
            b"$8\r\nbytesval\r\n"
        )
        assert encoded == expected

    def test_parse_resp_simple_string(self) -> None:
        stream = io.BytesIO(b"+OK\r\n")
        assert parse_resp(stream) == "OK"

    def test_parse_resp_error(self) -> None:
        stream = io.BytesIO(b"-ERR unknown command\r\n")
        with pytest.raises(ValkeyCommandError, match="unknown command"):
            parse_resp(stream)

    def test_parse_resp_integer(self) -> None:
        stream = io.BytesIO(b":1024\r\n")
        assert parse_resp(stream) == 1024

    def test_parse_resp_bulk_string(self) -> None:
        stream = io.BytesIO(b"$11\r\nhello world\r\n")
        assert parse_resp(stream) == "hello world"

    def test_parse_resp_null_bulk_string(self) -> None:
        stream = io.BytesIO(b"$-1\r\n")
        assert parse_resp(stream) is None

    def test_parse_resp_array(self) -> None:
        stream = io.BytesIO(b"*2\r\n$4\r\necho\r\n$2\r\nhi\r\n")
        assert parse_resp(stream) == ["echo", "hi"]

    def test_parse_resp_null_array(self) -> None:
        stream = io.BytesIO(b"*-1\r\n")
        assert parse_resp(stream) is None

    def test_parse_resp_empty_array(self) -> None:
        stream = io.BytesIO(b"*0\r\n")
        assert parse_resp(stream) == []

    def test_parse_resp_null_token(self) -> None:
        stream = io.BytesIO(b"_\r\n")
        assert parse_resp(stream) is None

    def test_parse_resp_boolean(self) -> None:
        assert parse_resp(io.BytesIO(b"#t\r\n")) is True
        assert parse_resp(io.BytesIO(b"#f\r\n")) is False

    def test_parse_resp_map(self) -> None:
        stream = io.BytesIO(b"%1\r\n+field\r\n$5\r\nvalue\r\n")
        assert parse_resp(stream) == {"field": "value"}

    def test_parse_resp_set(self) -> None:
        stream = io.BytesIO(b"~2\r\n+a\r\n+b\r\n")
        assert parse_resp(stream) == {"a", "b"}

    def test_parse_resp_unknown_prefix(self) -> None:
        stream = io.BytesIO(b"?unknown\r\n")
        with pytest.raises(ValkeyCommandError, match="Unknown RESP type prefix"):
            parse_resp(stream)

    def test_parse_resp_premature_eof(self) -> None:
        stream = io.BytesIO(b"")
        with pytest.raises(ValkeyConnectionError, match="Unexpected end of stream"):
            parse_resp(stream)

    def test_parse_info_response(self) -> None:
        info_raw = "# Server\r\nvalkey_version:8.0.0\r\nuptime_in_seconds:3600\r\n# Memory\r\nused_memory_human:1.2M\r\n"
        parsed = parse_info_response(info_raw)
        assert parsed["valkey_version"] == "8.0.0"
        assert parsed["uptime_in_seconds"] == "3600"
        assert parsed["used_memory_human"] == "1.2M"


# =============================================================================
# 2. ValkeyClient Socket & Command Tests
# =============================================================================


class TestValkeyClient:
    """Tests for TCP socket-based ValkeyClient."""

    def _mock_socket_connection(self, responses: list[bytes]) -> MagicMock:
        mock_sock = MagicMock()
        mock_file = io.BytesIO(b"".join(responses))
        mock_sock.makefile.return_value = mock_file
        return mock_sock

    def test_ping_success(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = self._mock_socket_connection([b"+PONG\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            assert client.ping() is True
        client.close()

    def test_ping_custom_message(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = self._mock_socket_connection([b"$4\r\nHELO\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            assert client.ping("HELO") is True
        client.close()

    def test_authentication_success(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379, password="secretpassword")
        mock_sock = self._mock_socket_connection([b"+OK\r\n", b"+PONG\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            assert client.ping() is True
        client.close()

    def test_authentication_failure(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379, password="badpassword")
        mock_sock = self._mock_socket_connection([b"-ERR invalid password\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            with pytest.raises(ValkeyAuthenticationError, match="Authentication failed"):
                client.ping()
        client.close()

    def test_db_selection(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379, db=3)
        mock_sock = self._mock_socket_connection([b"+OK\r\n", b"+PONG\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            assert client.ping() is True
        client.close()

    def test_get_and_set(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = self._mock_socket_connection([b"+OK\r\n", b"$5\r\nhello\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            assert client.set("key1", "hello", ex_seconds=60) is True
            assert client.get("key1") == "hello"
        client.close()

    def test_delete_and_keys(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = self._mock_socket_connection([b":2\r\n", b"*2\r\n$4\r\nkey1\r\n$4\r\nkey2\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            assert client.delete("key1", "key2") == 2
            assert client.keys("key*") == ["key1", "key2"]
        client.close()

    def test_flushdb_and_flushall(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = self._mock_socket_connection([b"+OK\r\n", b"+OK\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            assert client.flushdb() is True
            assert client.flushall() is True
        client.close()

    def test_dbsize_and_bgsave(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = self._mock_socket_connection([b":42\r\n", b"+Background saving started\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            assert client.dbsize() == 42
            assert "Background saving" in client.bgsave()
        client.close()

    def test_eval_lua(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = self._mock_socket_connection([b":1\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            res = client.eval("return 1", 0)
            assert res == 1
        client.close()

    def test_connection_error_on_socket_fail(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        with patch.object(client, "_create_socket", side_effect=OSError("Connection refused")):
            with pytest.raises(ValkeyConnectionError, match="Failed to connect to Valkey"):
                client.ping()
        client.close()

    def test_timeout_error_on_socket_timeout(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        with patch.object(
            client, "_create_socket", side_effect=TimeoutError("Connection timed out")
        ):
            with pytest.raises(ValkeyTimeoutError, match="timed out"):
                client.ping()
        client.close()

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
        with patch(
            "socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 6379))],
        ):
            with pytest.raises(
                ValkeyConnectionError, match="link-local metadata endpoints are prohibited"
            ):
                ValkeyClient(host="example.com", port=6379)

    def test_hostname_resolving_to_private_rejected_when_not_allowed(self) -> None:
        with patch(
            "socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 6379))],
        ):
            with pytest.raises(ValkeyConnectionError, match="non-public IP disallowed"):
                ValkeyClient(host="example.com", allow_private_network=False)

    def test_hostname_dns_failure_rejected_when_private_not_allowed(self) -> None:
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name or service not known")):
            with pytest.raises(ValkeyConnectionError, match="DNS resolution failed"):
                ValkeyClient(host="example.com", allow_private_network=False)

    def test_scan_and_scan_iter(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = self._mock_socket_connection(
            [
                b"*2\r\n$2\r\n10\r\n*2\r\n$4\r\nkey1\r\n$4\r\nkey2\r\n",
                b"*2\r\n$1\r\n0\r\n*1\r\n$4\r\nkey3\r\n",
            ]
        )
        with patch.object(client, "_create_socket", return_value=mock_sock):
            keys = client.scan_iter(match="key*")
            assert keys == ["key1", "key2", "key3"]
        client.close()

    def test_delete_empty_keys(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        assert client.delete() == 0
        client.close()

    def test_keys_non_list_response(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = self._mock_socket_connection([b"+OK\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            assert client.keys() == []
        client.close()

    def test_flushdb_and_flushall_async(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = self._mock_socket_connection([b"+OK\r\n", b"+OK\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            assert client.flushdb(asynchronous=True) is True
            assert client.flushall(asynchronous=True) is True
        client.close()

    def test_context_manager(self) -> None:
        mock_sock = self._mock_socket_connection([b"+PONG\r\n"])
        with patch("devops_cli.valkey.client.ValkeyClient._create_socket", return_value=mock_sock):
            with ValkeyClient(host="127.0.0.1", port=6379) as client:
                assert client.ping() is True

    def test_connect_idempotent(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = self._mock_socket_connection([b"+OK\r\n"])
        with patch.object(client, "_create_socket", return_value=mock_sock):
            client.connect()
            # Second connect call should return immediately without creating another socket
            client.connect()
        client.close()

    def test_execute_broken_pipe(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = MagicMock()
        mock_sock.sendall.side_effect = BrokenPipeError("Broken pipe")
        with patch.object(client, "_create_socket", return_value=mock_sock):
            with pytest.raises(ValkeyConnectionError, match="Connection dropped"):
                client.execute("PING")
        client.close()

    def test_execute_timeout(self) -> None:
        client = ValkeyClient(host="127.0.0.1", port=6379)
        mock_sock = MagicMock()
        mock_sock.sendall.side_effect = TimeoutError("Timed out")
        with patch.object(client, "_create_socket", return_value=mock_sock):
            with pytest.raises(ValkeyTimeoutError, match="timed out"):
                client.execute("PING")
        client.close()


# =============================================================================
# 3. Rate Limiter Tests
# =============================================================================


class TestValkeyRateLimiter:
    """Tests for atomic token-bucket sliding-window rate limiter."""

    def test_rate_limiter_allows_tokens(self) -> None:
        mock_client = MagicMock()
        mock_client.eval.return_value = [1, 9]
        limiter = ValkeyTokenBucketRateLimiter(
            client=mock_client,
            rate_limit_per_second=10.0,
            burst_capacity=10,
        )
        assert limiter.acquire("user:1", tokens=1) is True

    def test_rate_limiter_exhausted(self) -> None:
        mock_client = MagicMock()
        mock_client.eval.return_value = [0, 0]
        limiter = ValkeyTokenBucketRateLimiter(
            client=mock_client,
            rate_limit_per_second=5.0,
            burst_capacity=5,
        )
        assert limiter.acquire("user:1", tokens=1) is False

    def test_rate_limiter_fail_soft_on_error(self) -> None:
        mock_client = MagicMock()
        mock_client.eval.side_effect = ValkeyConnectionError("Valkey is down")
        limiter = ValkeyTokenBucketRateLimiter(
            client=mock_client,
            rate_limit_per_second=10.0,
            burst_capacity=10,
        )
        # In fail-soft mode, traffic must not be blocked when caching tier drops
        assert limiter.acquire("user:1", tokens=1) is True

    def test_rate_limiter_raises_on_programmer_error(self) -> None:
        mock_client = MagicMock()
        mock_client.eval.side_effect = TypeError("Unexpected parameter type")
        limiter = ValkeyTokenBucketRateLimiter(
            client=mock_client,
            rate_limit_per_second=10.0,
            burst_capacity=10,
        )
        with pytest.raises(TypeError):
            limiter.acquire("user:1", tokens=1)


# =============================================================================
# 4. Distributed AI Cache Provider Tests
# =============================================================================


class TestValkeyCacheProvider:
    """Tests for ValkeyCacheProvider embedding and finding cache."""

    def test_cache_provider_availability(self) -> None:
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        provider = ValkeyCacheProvider(client=mock_client)
        assert provider.is_available() is True

        mock_client.ping.side_effect = ValkeyConnectionError("Offline")
        assert provider.is_available() is False

    def test_embedding_caching_roundtrip(self) -> None:
        mock_client = MagicMock()
        mock_client.get.return_value = "[0.12, 0.34, 0.56]"
        mock_client.set.return_value = True

        provider = ValkeyCacheProvider(client=mock_client)
        vec = provider.get_embedding("hello world", "bge-m3")
        assert vec == [0.12, 0.34, 0.56]

        assert provider.set_embedding("hello world", "bge-m3", [0.12, 0.34, 0.56]) is True
        mock_client.set.assert_called_once()

    def test_review_findings_caching(self) -> None:
        mock_client = MagicMock()
        mock_client.get.return_value = '[{"rule_id": "SEC-01", "severity": "HIGH"}]'
        mock_client.set.return_value = True

        provider = ValkeyCacheProvider(client=mock_client)
        findings = provider.get_review_findings("src/main.py", "abc123hash", "devsecops")
        assert findings == [{"rule_id": "SEC-01", "severity": "HIGH"}]

        assert (
            provider.set_review_findings("src/main.py", "abc123hash", "devsecops", findings) is True
        )

    def test_llm_response_caching(self) -> None:
        mock_client = MagicMock()
        mock_client.get.return_value = '{"response": "Cached answer"}'
        mock_client.set.return_value = True

        provider = ValkeyCacheProvider(client=mock_client)
        assert provider.get_llm_response("query_hash") == {"response": "Cached answer"}
        assert provider.set_llm_response("query_hash", {"response": "Cached answer"}) is True

    def test_flush_ai_cache(self) -> None:
        mock_client = MagicMock()
        mock_client.scan_iter.return_value = ["devops:ai:embedding:1", "devops:ai:finding:2"]
        mock_client.delete.return_value = 2

        provider = ValkeyCacheProvider(client=mock_client)
        assert provider.flush_ai_cache() == 2

    def test_get_stats(self) -> None:
        mock_client = MagicMock()
        mock_client.info.return_value = {
            "used_memory_human": "2.4M",
            "total_system_memory_human": "16G",
        }
        mock_client.scan_iter.return_value = ["key1", "key2"]

        provider = ValkeyCacheProvider(client=mock_client)
        stats = provider.get_stats()
        assert stats["available"] is True
        assert stats["ai_keys_count"] == 2
        assert stats["used_memory_human"] == "2.4M"


# =============================================================================
# 5. CLI Command Tests
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

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_set(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["set", "k", "v", "--ex", "30"])
        assert res.exit_code == 0
        assert "Set 'k' successfully" in res.output

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

    @patch("devops_cli.commands.valkey._resolve_client")
    def test_cli_raw_execution(self, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.execute.return_value = ["item1", "item2"]
        mock_resolve.return_value = mock_client

        res = runner.invoke(app, ["cli", "LRANGE", "mylist", "0", "1"])
        assert res.exit_code == 0
        assert "item1" in res.output
        assert "item2" in res.output

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
