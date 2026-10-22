"""Valkey access: valkey-py behind the egress check and the repo's exception types."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, suppress
from functools import partial
from itertools import batched
from typing import Any
from urllib.parse import urlsplit

import valkey
from valkey import exceptions as valkey_exceptions
from valkey.connection import Connection

from devops_cli.config.constants import CONST_VALKEY_SCHEMES
from devops_cli.config.defaults import (
    DEFAULT_VALKEY_HOST,
    DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS,
    DEFAULT_VALKEY_PORT,
    DEFAULT_VALKEY_SCAN_COUNT,
    DEFAULT_VALKEY_TIMEOUT_SECONDS,
)
from devops_cli.core.validation import is_non_public_ip
from devops_cli.exceptions.valkey import (
    ValkeyAuthenticationError,
    ValkeyCommandError,
    ValkeyConnectionError,
    ValkeyTimeoutError,
)


def parse_valkey_endpoint(
    endpoint: str, default_port: int = DEFAULT_VALKEY_PORT
) -> tuple[str, int]:
    """Parse a hostname, hostname:port, or Valkey/Redis URI into host and port."""
    if not isinstance(endpoint, str):
        return endpoint, default_port
    clean = endpoint.strip()
    scheme = urlsplit(clean).scheme.lower()
    target = clean if scheme in CONST_VALKEY_SCHEMES else f"//{clean}"
    try:
        parsed = urlsplit(target)
        host = parsed.hostname or clean
        port = parsed.port if parsed.port is not None else default_port
        return host, port
    except ValueError, AttributeError:
        return clean, default_port


def _resolved_addresses(
    host: str, port: int, allow_private_network: bool
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Every address a host names: the literal itself, or what the resolver answers."""
    with suppress(ValueError):
        return [ipaddress.ip_address(host)]
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        if allow_private_network:
            return []
        raise ValkeyConnectionError(
            f"Invalid or unresolvable host '{host}': DNS resolution failed under non-private egress policy."
        ) from exc
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for answer in answers:
        with suppress(ValueError):
            addresses.append(ipaddress.ip_address(answer[4][0]))
    return addresses


def validate_destination(host: str, port: int, allow_private_network: bool = True) -> None:
    """Refuse a link-local destination always, and a non-public one unless private networks are allowed."""
    if not host.strip():
        raise ValkeyConnectionError("Invalid host: host cannot be empty.")
    for address in _resolved_addresses(host.strip(), port, allow_private_network):
        if address.is_link_local:
            raise ValkeyConnectionError(
                f"Invalid or prohibited host '{host}': link-local metadata endpoints are prohibited."
            )
        if not allow_private_network and is_non_public_ip(address):
            raise ValkeyConnectionError(
                f"Invalid or prohibited host '{host}': non-public IP disallowed by egress policy."
            )


def _invoke(command: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call into valkey-py, whose functions carry no annotations, and type the result as Any."""
    return command(*args, **kwargs)


class _GuardedConnection(Connection):
    """A valkey-py connection that checks its destination again each time it dials."""

    def __init__(self, *args: Any, allow_private_network: bool = True, **kwargs: Any) -> None:
        _invoke(super().__init__, *args, **kwargs)
        self._allow_private_network = allow_private_network

    def connect(self) -> None:
        """Check the destination, then dial it, unless the connection is already open."""
        if self._sock is None:
            validate_destination(self.host, self.port, self._allow_private_network)
        _invoke(super().connect)


@contextmanager
def _valkey_failures(host: str, port: int, timeout: float) -> Iterator[None]:
    """Raise the repo's ValkeyError family for a failure valkey-py reports."""
    try:
        yield
    except valkey_exceptions.AuthenticationError as exc:
        raise ValkeyAuthenticationError(
            f"Authentication failed for Valkey at {host}:{port}: {exc}", host=host, port=port
        ) from exc
    except valkey_exceptions.TimeoutError as exc:
        raise ValkeyTimeoutError(
            f"Valkey at {host}:{port} timed out after {timeout}s.",
            timeout_seconds=timeout,
            details={"host": host, "port": port},
        ) from exc
    except valkey_exceptions.ConnectionError as exc:
        raise ValkeyConnectionError(
            f"Failed to connect to Valkey at {host}:{port}: {exc}", host=host, port=port
        ) from exc
    except valkey_exceptions.ValkeyError as exc:
        raise ValkeyCommandError(str(exc)) from exc


class ValkeyClient:
    """The Valkey commands devops-cli runs, sent by valkey-py after the egress check.

    Construction checks the destination without connecting; every connection checks it again
    when it dials. Failures raise the `ValkeyError` family. `execute` returns replies as the
    server sent them, decoded to text; the named commands return what valkey-py parses.
    `connection_pool` replaces the pool the client builds from the endpoint, which is how a
    test connects it to an in-memory server.
    """

    def __init__(
        self,
        host: str = DEFAULT_VALKEY_HOST,
        port: int = DEFAULT_VALKEY_PORT,
        password: str | None = None,
        db: int = 0,
        timeout: float = DEFAULT_VALKEY_TIMEOUT_SECONDS,
        allow_private_network: bool = True,
        connection_pool: valkey.ConnectionPool | None = None,
    ) -> None:
        self.host, self.port = parse_valkey_endpoint(host, default_port=port)
        self.db = db
        self.timeout = timeout
        validate_destination(self.host, self.port, allow_private_network)
        pool = connection_pool or valkey.ConnectionPool(
            connection_class=partial(
                _GuardedConnection, allow_private_network=allow_private_network
            ),
            host=self.host,
            port=self.port,
            db=db,
            password=password,
            socket_timeout=timeout,
            socket_connect_timeout=timeout,
            decode_responses=True,
            encoding_errors="replace",
        )
        self._valkey = valkey.Valkey(connection_pool=pool)
        self._raw = valkey.Valkey(connection_pool=pool)
        self._raw.response_callbacks.clear()

    def _call(self, command: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run one valkey-py call, raising ValkeyError subclasses for its failures."""
        with _valkey_failures(self.host, self.port, self.timeout):
            return command(*args, **kwargs)

    def execute(self, *parts: Any) -> Any:
        """Send one command and return its reply as the server sent it."""
        return self._call(self._raw.execute_command, *parts)

    def pipeline(self, commands: Sequence[Sequence[Any]]) -> list[Any]:
        """Send commands in batches of one round trip each, without MULTI/EXEC; return the replies."""
        replies: list[Any] = []
        for batch in batched(commands, DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS, strict=False):
            queue = self._raw.pipeline(transaction=False)
            for command in batch:
                self._call(queue.execute_command, *command)
            replies.extend(self._call(queue.execute))
        return replies

    def ping(self) -> bool:
        """Whether the server answers PING."""
        return bool(self._call(self._valkey.ping))

    def info(self, section: str | None = None) -> dict[str, Any]:
        """Server telemetry, as valkey-py parses INFO."""
        return dict(self._call(self._valkey.info, section))

    def get(self, key: str) -> str | None:
        """The string at a key, or None."""
        value = self._call(self._valkey.get, key)
        return None if value is None else str(value)

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """Set a string, expiring after `ex` seconds when given."""
        return bool(self._call(self._valkey.set, key, value, ex=ex))

    def delete(self, *keys: str) -> int:
        """Remove keys; the number removed."""
        return int(self._call(self._valkey.delete, *keys))

    def keys(self, pattern: str) -> list[str]:
        """Every key matching a glob pattern."""
        return list(self._call(self._valkey.keys, pattern))

    def scan_iter(
        self, match: str | None = None, count: int = DEFAULT_VALKEY_SCAN_COUNT
    ) -> Iterator[str]:
        """Matching keys, found by SCAN without blocking the server."""
        with _valkey_failures(self.host, self.port, self.timeout):
            yield from self._valkey.scan_iter(match=match, count=count)

    def dbsize(self) -> int:
        """The number of keys in the current database."""
        return int(self._call(self._valkey.dbsize))

    def flushdb(self) -> bool:
        """Delete every key in the current database."""
        return bool(self._call(self._valkey.flushdb))

    def flushall(self) -> bool:
        """Delete every key in every database."""
        return bool(self._call(self._valkey.flushall))

    def bgsave(self) -> str:
        """Start a background snapshot; the server's acknowledgement."""
        return str(self.execute("BGSAVE"))

    def close(self) -> None:
        """Close every connection the client holds."""
        self._valkey.connection_pool.disconnect()
