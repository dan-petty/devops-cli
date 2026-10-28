"""Valkey access: valkey-py behind the egress check and the repo's exception types.

valkey-py resolves the host itself when it dials, so a check that resolves the host before the
dial leaves a window: a rebinding DNS server can give the dial an address that the check did not
see. The connection classes here resolve the host once, when they dial, with `vet_addresses` at
the private egress level, and connect only to the vetted IP literals. Valkey is an internal
service, so every address but a cloud metadata address and a scoped IPv6 address is admitted. This
includes the link-local 169.254.1.2 that a rootless Podman container reaches its host at.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from itertools import batched
from typing import Any

import httpcore2
import valkey
from valkey import exceptions as valkey_exceptions
from valkey.connection import Connection, SSLConnection

from devops_cli.config.defaults import (
    DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS,
)
from devops_cli.exceptions import SSRFBlockedError
from devops_cli.exceptions.valkey import (
    ValkeyAuthenticationError,
    ValkeyCommandError,
    ValkeyConnectionError,
    ValkeyTimeoutError,
)
from devops_cli.http.egress import EgressLevel, vet_addresses
from devops_cli.valkey.endpoint import ValkeyEndpoint


class _VettedConnection(Connection):
    """A valkey-py connection that resolves its host once for each dial and dials a vetted address.

    valkey-py's own dial would resolve the host again. This dial tries each address that
    `vet_addresses` returns, in answer order, as `socket.create_connection` tries the answers of a
    name, and raises the last failure. An unsafe answer raises `SSRFBlockedError` and a failed lookup
    raises `httpcore2.ConnectError`, before a socket opens. valkey-py does not catch either, and
    `_valkey_failures` makes each a `ValkeyConnectionError`. The client sets no keepalive options,
    so the dial sets none.
    """

    def _connect(self) -> socket.socket:
        failures: list[OSError] = []
        for address in vet_addresses(self.host, self.port, EgressLevel.PRIVATE):
            ip_version = ipaddress.ip_address(address).version
            sock = socket.socket(socket.AF_INET6 if ip_version == 6 else socket.AF_INET)
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.settimeout(self.socket_connect_timeout)
                sock.connect((address, self.port))
            except OSError as exc:
                sock.close()
                failures.append(exc)
                continue
            sock.settimeout(self.socket_timeout)
            return sock
        raise failures[-1]


class _VettedSSLConnection(SSLConnection, _VettedConnection):
    """The TLS connection: `SSLConnection` wraps the socket of the vetted dial.

    `SSLConnection._connect` gets its socket from the next class in the method resolution order,
    which is `_VettedConnection`. The TCP connection goes to the vetted IP literal. The handshake
    sends `self.host`, the name of the endpoint, as the server name and checks the certificate
    against it.
    """


@contextmanager
def _valkey_failures(host: str, port: int, timeout: float) -> Iterator[None]:
    """Raise the repo's ValkeyError family for a failure valkey-py or the egress check reports."""
    try:
        yield
    except SSRFBlockedError as exc:
        raise ValkeyConnectionError(
            f"The egress check refuses Valkey at {host}:{port}: {exc.details['reason']}.",
            host=host,
            port=port,
        ) from exc
    except httpcore2.ConnectError as exc:
        raise ValkeyConnectionError(
            f"Cannot resolve the Valkey host {host}: {exc}", host=host, port=port
        ) from exc
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
    """The Valkey commands devops-cli runs, sent by valkey-py over vetted connections.

    The client dials the endpoint of one validated Valkey URL (`parse_valkey_url`). Construction
    makes no DNS lookup and opens no connection. Each connection resolves the host once when it
    dials, vets every answer, and dials a vetted address, and then selects the database of the
    endpoint. A `valkeys://` endpoint connects over TLS, which sends the endpoint's host name as
    the server name and checks the certificate against it with the platform CA store. Failures
    raise the `ValkeyError` family. `execute` returns replies as the server sent them, decoded to
    text; the named commands return what valkey-py parses. `connection_pool` replaces the pool the
    client builds from the endpoint, which is how a test connects it to an in-memory server.
    """

    def __init__(
        self,
        endpoint: ValkeyEndpoint,
        *,
        password: str | None = None,
        timeout: float | None = None,
        connection_pool: valkey.ConnectionPool | None = None,
    ) -> None:
        if timeout is None:
            # `valkey.timeout` of the loaded settings when the caller gives none (#2447).
            from devops_cli.config.settings import load_settings

            timeout = load_settings().valkey.timeout
        self.host, self.port, self.db = endpoint.host, endpoint.port, endpoint.db
        self.timeout = timeout
        connection: dict[str, Any] = (
            {"connection_class": _VettedSSLConnection, "ssl_check_hostname": True}
            if endpoint.tls
            else {"connection_class": _VettedConnection}
        )
        pool = connection_pool or valkey.ConnectionPool(
            host=self.host,
            port=self.port,
            db=self.db,
            password=password,
            socket_timeout=timeout,
            socket_connect_timeout=timeout,
            decode_responses=True,
            encoding_errors="replace",
            **connection,
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

    def keys(self, pattern: str) -> list[str]:
        """Every key matching a glob pattern."""
        return list(self._call(self._valkey.keys, pattern))

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
