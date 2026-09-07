"""Pure-Python synchronous Valkey and Redis client over standard TCP sockets."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any

from devops_cli.core.validation import is_non_public_ip
from devops_cli.exceptions.valkey import (
    ValkeyAuthenticationError,
    ValkeyCommandError,
    ValkeyConnectionError,
    ValkeyTimeoutError,
)
from devops_cli.valkey.protocol import encode_command, parse_resp


def parse_info_response(info_text: str) -> dict[str, str]:
    """Parse Valkey INFO text into key-value pairs."""
    result: dict[str, str] = {}
    for line in (info_text or "").splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        if ":" in cleaned:
            k, v = cleaned.split(":", 1)
            result[k.strip()] = v.strip()
    return result


class ValkeyClient:
    """Lightweight pure-Python client for Valkey using RESP2/RESP3 wire protocol."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: str | None = None,
        db: int = 0,
        timeout: float = 2.0,
        allow_private_network: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.timeout = timeout
        self.allow_private_network = allow_private_network
        self._sock: socket.socket | None = None
        self._reader: Any = None
        self._validate_destination()

    def _validate_destination(self) -> None:
        """Validate target host safety against SSRF and metadata attack vectors."""
        clean_host = self.host.strip()
        if not clean_host:
            raise ValkeyConnectionError("Invalid host: host cannot be empty.")
        try:
            ip = ipaddress.ip_address(clean_host)
            if ip.is_link_local:
                raise ValkeyConnectionError(
                    f"Invalid or prohibited host '{self.host}': link-local metadata endpoints are prohibited."
                )
            if not self.allow_private_network and is_non_public_ip(ip):
                raise ValkeyConnectionError(
                    f"Invalid or prohibited host '{self.host}': non-public IP disallowed by egress policy."
                )
        except ValueError:
            pass

    def _create_socket(self) -> socket.socket:
        """Create connected socket instance."""
        return socket.create_connection((self.host, self.port), timeout=self.timeout)

    def connect(self) -> None:
        """Establish connection to Valkey instance and authenticate."""
        if self._sock is not None:
            return

        self._validate_destination()
        try:
            sock = self._create_socket()
            sock.settimeout(self.timeout)
            self._sock = sock
            self._reader = sock.makefile("rb")

            if self.password:
                self._authenticate()

            if self.db != 0:
                self.execute("SELECT", self.db)

        except TimeoutError as exc:
            self.close()
            raise ValkeyTimeoutError(
                f"Connection to Valkey at {self.host}:{self.port} timed out after {self.timeout}s.",
                timeout_seconds=self.timeout,
                details={"host": self.host, "port": self.port},
            ) from exc
        except ValkeyAuthenticationError:
            self.close()
            raise
        except OSError as exc:
            self.close()
            raise ValkeyConnectionError(
                f"Failed to connect to Valkey at {self.host}:{self.port}: {exc}",
                host=self.host,
                port=self.port,
            ) from exc

    def _authenticate(self) -> None:
        """Authenticate connection using configured password."""
        try:
            self.execute("AUTH", self.password)
        except ValkeyCommandError as exc:
            raise ValkeyAuthenticationError(
                f"Authentication failed for Valkey at {self.host}:{self.port}: {exc}",
                host=self.host,
                port=self.port,
            ) from exc

    def execute(self, *parts: Any) -> Any:
        """Send command and read decoded response from Valkey server."""
        if self._sock is None or self._reader is None:
            self.connect()

        try:
            payload = encode_command(*parts)
            assert self._sock is not None
            self._sock.sendall(payload)
            assert self._reader is not None
            return parse_resp(self._reader)
        except TimeoutError as exc:
            self.close()
            raise ValkeyTimeoutError(
                f"Valkey command '{parts[0]}' timed out after {self.timeout}s.",
                timeout_seconds=self.timeout,
            ) from exc
        except (OSError, BrokenPipeError, ConnectionResetError) as exc:
            self.close()
            raise ValkeyConnectionError(
                f"Connection dropped while executing Valkey command '{parts[0]}': {exc}",
                host=self.host,
                port=self.port,
            ) from exc

    def ping(self, message: str | None = None) -> bool:
        """Test server responsiveness via PING command."""
        cmd = ["PING", message] if message else ["PING"]
        res = self.execute(*cmd)
        return res == "PONG" or res == message or res is True

    def info(self, section: str | None = None) -> dict[str, str]:
        """Fetch server telemetry, properties, and statistics."""
        args = ["INFO", section] if section else ["INFO"]
        raw = self.execute(*args)
        return parse_info_response(str(raw))

    def get(self, key: str) -> str | None:
        """Retrieve value associated with key."""
        res = self.execute("GET", key)
        return str(res) if res is not None else None

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        ex_seconds: int | None = None,
    ) -> bool:
        """Set key to hold string value with optional expiration seconds."""
        effective_ttl = ex_seconds if ex_seconds is not None else ttl
        args: list[Any] = ["SET", key, str(value)]
        if effective_ttl is not None and effective_ttl > 0:
            args.extend(["EX", effective_ttl])
        res = self.execute(*args)
        return res == "OK" or res is True

    def delete(self, *keys: str) -> int:
        """Remove specified keys."""
        if not keys:
            return 0
        res = self.execute("DEL", *keys)
        return int(res) if isinstance(res, (int, float)) else 0

    def keys(self, pattern: str = "*") -> list[str]:
        """Find all keys matching the given pattern."""
        res = self.execute("KEYS", pattern)
        if isinstance(res, list):
            return [str(k) for k in res]
        return []

    def flushdb(self, asynchronous: bool = False) -> bool:
        """Delete all keys from the current database."""
        args = ["FLUSHDB", "ASYNC"] if asynchronous else ["FLUSHDB"]
        res = self.execute(*args)
        return res == "OK" or res is True

    def flushall(self, asynchronous: bool = False) -> bool:
        """Delete all keys from all databases."""
        args = ["FLUSHALL", "ASYNC"] if asynchronous else ["FLUSHALL"]
        res = self.execute(*args)
        return res == "OK" or res is True

    def dbsize(self) -> int:
        """Return the total number of keys in the current database."""
        res = self.execute("DBSIZE")
        return int(res) if isinstance(res, (int, float)) else 0

    def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any:
        """Execute Lua script atomically on the Valkey server."""
        return self.execute("EVAL", script, numkeys, *keys_and_args)

    def bgsave(self) -> str:
        """Trigger asynchronous background snapshot save to disk."""
        return str(self.execute("BGSAVE"))

    def close(self) -> None:
        """Close socket and reader cleanly."""
        if self._reader is not None:
            try:
                self._reader.close()
            except Exception:
                pass
            self._reader = None

        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def __enter__(self) -> ValkeyClient:
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
