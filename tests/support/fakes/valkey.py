"""Valkey faked in memory for tests: a server, and `ValkeyClient`s connected to it (#1113, ADR 0007).

The server is fakeredis's in-memory Valkey (`FakeServer`), which answers the commands the
client sends and records nothing else. A `ValkeyClient` reaches it through the `connection_pool`
seam, so the client's own code runs for real: its reply handling, its batching, and its mapping
of failures onto `ValkeyError`. Nothing opens a socket.

Its contract suite, `tests/valkey/test_valkey_contract.py`, runs each scenario of
`tests/support/valkey_scenarios.py` over the fake and over the recorded replies of a real
`valkey-server` (#4557). fakeredis runs Lua through its `lua` extra (`lupa`), and holds its
server to Valkey's behaviour in its own test suite. It answers no INFO, and
holds a silent or slow server only as a connection that fails; a test of a timeout binds a
loopback listener that never answers (`silent_valkey`), as the floor's `refusing_port` does for a
refused port. `shared_valkey` installs a cache tier over the fake as the one tier of the process,
which the shared tier of the project brain reads (#4668), and `roadmap_state_valkey` installs one
as the tier of the roadmap state, which the brain index reads and writes (#4676). A client of
`valkey_client_on` with `transactions` records the commands of each MULTI/EXEC block that it
sends. A client of `valkey_client_on` with
`after_command` runs a test action after each command that it sends alone, so a test changes
the world between a WATCH and its EXEC, or between two `HSCAN` steps, with no double of its own.
The pool is the fake's own, so a test of what the client's own password, the database of its
endpoint and its decoding send and read binds a loopback listener that records the commands it
receives. That
listener is `serving_valkey`. A test of INFO uses it too. It replies with the text of a server,
and the client's own parser turns that text into the mapping the test reads. A test of a
`valkeys://` endpoint gives `serving_valkey` a TLS context from `tests/support/certificates.py`.
"""

from __future__ import annotations

import socket
import ssl
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import pytest
from fakeredis import FakeServer, FakeValkey
from redis.exceptions import ConnectionError as RedisConnectionError
from valkey import exceptions as valkey_exceptions

from devops_cli.valkey.client import ValkeyClient
from tests.support.waits import POLL_INTERVAL_SECONDS, THREAD_HANDOFF_BOUND_SECONDS

if TYPE_CHECKING:
    from devops_cli.valkey.cache import ValkeyCacheTier
    from devops_cli.valkey.endpoint import ValkeyEndpoint


def valkey_endpoint(url: str) -> ValkeyEndpoint:
    """The endpoint that a Valkey URL names, validated as `valkey.url` is.

    The import is local, so the fail-to-pass replay can load this plugin on a base without the
    module.
    """
    from devops_cli.valkey.endpoint import parse_valkey_url

    return parse_valkey_url(url, setting="valkey.url")


AfterCommand = Callable[[tuple[Any, ...]], None]
"""A test action that runs after the server did one command that a client sent alone: it gets
the words of the command, such as `("HGET", key, field)`."""


def valkey_client_on(
    server: FakeServer,
    *,
    password: str | None = None,
    after_command: AfterCommand | None = None,
    transactions: list[list[list[str]]] | None = None,
) -> ValkeyClient:
    """A `ValkeyClient` connected to an in-memory server.

    The pool is the fake's own, so the client's password, the database of its endpoint and its
    decoding play no part.

    `after_command` runs after the server did each command that the client sends alone, and
    before the client reads the reply: a plain command, and the WATCH and each read of a WATCH
    transaction before its MULTI. It does not see the commands of a MULTI/EXEC block. A test uses
    it to change the world at that point: another client writes the watched key before the EXEC,
    `server.connected = False` stops the server before the next command, or the `clock` fixture
    moves between two `HSCAN` steps.

    `transactions` gets the commands of each MULTI/EXEC block that the client sends, from `MULTI`
    to `EXEC`, each command as its words. A test reads from it which keys one transaction wrote.
    """
    pool = FakeValkey(
        server=server, password=password, decode_responses=True, encoding_errors="replace"
    ).connection_pool
    pool.connection_class = _fake_connection_class(
        pool.connection_class, after_command, transactions
    )
    return ValkeyClient(valkey_endpoint("valkey://127.0.0.1"), connection_pool=pool)


def _fake_connection_class(
    base: type[Any],
    after_command: AfterCommand | None,
    transactions: list[list[list[str]]] | None = None,
) -> type[Any]:
    """The connection class of the fake, with `after_command` after each command sent alone, and
    with each MULTI/EXEC block that it sends kept in `transactions`.

    The fake's server does a command while the client sends it, so the action sees its effect.
    A connection that is open when `server.connected` turns False fails its next write with the
    `ConnectionError` of redis-py from fakeredis's socket, where a real socket fails with an
    `OSError` that valkey-py gives as its own `ConnectionError`. The class gives valkey-py's.
    """

    class _FakeConnection(base):  # type: ignore[misc, valid-type]
        def send_command(self, *args: Any, **kwargs: Any) -> None:
            super().send_command(*args, **kwargs)
            if after_command is not None:
                after_command(args)

        def send_packed_command(self, command: Any, check_health: bool = True) -> None:
            if transactions is not None:
                packed = command if isinstance(command, bytes) else b"".join(command)
                sent = _commands_in(packed)
                if sent[:1] == [["MULTI"]]:
                    transactions.append(sent)
            try:
                super().send_packed_command(command, check_health)
            except RedisConnectionError as exc:
                raise valkey_exceptions.ConnectionError(str(exc)) from exc

    return _FakeConnection


@pytest.fixture
def valkey_server() -> FakeServer:
    """An empty in-memory Valkey server that needs no password."""
    return FakeServer(server_type="valkey")


@pytest.fixture
def valkey_client(valkey_server: FakeServer) -> Iterator[ValkeyClient]:
    """A client connected to `valkey_server`, closed after the test."""
    client = valkey_client_on(valkey_server)
    yield client
    client.close()


@pytest.fixture
def valkey(valkey_server: Any) -> Iterator[Any]:
    """Install an in-memory Valkey client as the Valkey seam override, and return it."""
    from devops_cli.valkey.client import install_valkey_client, reset_valkey_client

    client = valkey_client_on(valkey_server)
    install_valkey_client(client)
    try:
        yield client
    finally:
        reset_valkey_client()
        client.close()


@pytest.fixture
def shared_valkey(valkey_server: FakeServer) -> Iterator[ValkeyCacheTier]:
    """A cache tier over `valkey_server`, installed as the one tier of the process.

    `shared_cache_tier()` gives it, so each cache of the process reads and writes the fake. The
    imports are local, so the fail-to-pass replay can load this plugin on a base without the seam.
    """
    from devops_cli.valkey.cache import (
        ValkeyCacheTier,
        install_shared_cache_tier,
        reset_shared_cache_tier,
    )

    client = valkey_client_on(valkey_server)
    tier = ValkeyCacheTier(client)
    install_shared_cache_tier(tier)
    try:
        yield tier
    finally:
        reset_shared_cache_tier()
        client.close()


@pytest.fixture
def roadmap_state_valkey(valkey_server: FakeServer) -> Iterator[ValkeyCacheTier]:
    """A tier over `valkey_server`, installed as the tier of the roadmap state of the process.

    `roadmap_state_tier()` gives it, so the brain index of the alternatives results reads and
    writes the fake (#4676). The imports are local, so the fail-to-pass replay can load this
    plugin on a base without the seam.
    """
    from devops_cli.valkey.cache import (
        ValkeyCacheTier,
        install_roadmap_state_tier,
        reset_roadmap_state_tier,
    )

    client = valkey_client_on(valkey_server)
    tier = ValkeyCacheTier(client)
    install_roadmap_state_tier(tier)
    try:
        yield tier
    finally:
        reset_roadmap_state_tier()
        client.close()


class SilentValkey:
    """A loopback listener that accepts each connection and never answers: a silent Valkey host.

    `port` is its port, and `connections` counts the connections that it accepted.
    """

    def __init__(self, listener: socket.socket) -> None:
        self._listener = listener
        self._held: list[socket.socket] = []
        self._ended = threading.Event()
        self.port: int = listener.getsockname()[1]
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()

    @property
    def connections(self) -> int:
        return len(self._held)

    def _accept(self) -> None:
        self._listener.settimeout(POLL_INTERVAL_SECONDS)
        while not self._ended.is_set():
            try:
                connection, _ = self._listener.accept()
            except TimeoutError:
                continue
            self._held.append(connection)

    def close(self) -> None:
        self._ended.set()
        self._thread.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
        for connection in self._held:
            connection.close()


@pytest.fixture
def silent_valkey() -> Iterator[SilentValkey]:
    """A loopback Valkey host that accepts a connection and answers no command."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(8)
        silent = SilentValkey(listener)
        try:
            yield silent
        finally:
            silent.close()


def bulk_reply(payload: bytes) -> bytes:
    """A RESP bulk string reply."""
    return b"$%d\r\n%s\r\n" % (len(payload), payload)


def _commands_in(request: bytes) -> list[list[str]]:
    """The commands in the bytes a client sent: an array header, then a bulk string per word."""
    lines = request.decode().split("\r\n")
    commands: list[list[str]] = []
    position = 0
    while position < len(lines) and lines[position].startswith("*"):
        words = int(lines[position][1:])
        commands.append(lines[position + 2 : position + 1 + 2 * words : 2])
        position += 1 + 2 * words
    return commands


@contextmanager
def serving_valkey(
    replies: Mapping[str, bytes] | None = None,
    tls: ssl.SSLContext | None = None,
) -> Iterator[tuple[int, list[list[str]]]]:
    """A loopback server that records the commands it receives and answers each from `replies`.

    `replies` maps an upper-case command name to its RESP reply; any other command is answered
    +OK. The yielded record is complete once the block exits, which waits for the client to close
    its connection. A block in which no client connected exits at once, and the record is empty.
    valkey-py announces its name and version with `CLIENT SETINFO` after it connects; the record
    leaves those out.

    With `tls`, the server does the TLS handshake with that context before it reads a command. When
    the client refuses the handshake, the server closes the connection and records no command.
    """
    answers = replies or {}
    received: list[list[str]] = []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)

        ended = threading.Event()

        def serve() -> None:
            listener.settimeout(POLL_INTERVAL_SECONDS)
            while True:
                try:
                    connection, _ = listener.accept()
                    break
                except TimeoutError:
                    # A client that dialled before the block ended waits in the backlog, so the
                    # accept after the end finds it; only an empty backlog stops the server.
                    if ended.is_set():
                        return
            if tls is not None:
                try:
                    connection = tls.wrap_socket(connection, server_side=True)
                except ssl.SSLError:
                    connection.close()
                    return
            with connection:
                while request := connection.recv(4096):
                    commands = _commands_in(request)
                    received.extend(c for c in commands if c[:2] != ["CLIENT", "SETINFO"])
                    connection.sendall(
                        b"".join(
                            answers.get(command[0].upper(), b"+OK\r\n") for command in commands
                        )
                    )

        server = threading.Thread(target=serve, daemon=True)
        server.start()
        try:
            yield listener.getsockname()[1], received
        finally:
            ended.set()
            server.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
