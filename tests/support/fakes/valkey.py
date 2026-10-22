"""Valkey faked in memory for tests: a server, and `ValkeyClient`s connected to it (#1113, ADR 0007).

The server is fakeredis's in-memory Valkey (`FakeServer`), which answers the commands the
client sends and records nothing else. A `ValkeyClient` reaches it through the `connection_pool`
seam, so the client's own code runs for real: its reply handling, its batching, and its mapping
of failures onto `ValkeyError`. Nothing opens a socket.

The fake has no contract suite yet: a Valkey server is a daemon, and no recorded exchange or
local tool stands in for one (ADR 0007 lists contract suites for most edges under "Not yet").
fakeredis holds its server to Valkey's behaviour in its own test suite. It answers no INFO, and
holds a silent or slow server only as a connection that fails; a test of a timeout binds a
loopback listener that never answers, as the floor's `refusing_port` does for a refused port.
The pool is the fake's own, so a test of what the client's own `password`, `db` and decoding
arguments send and read binds a loopback listener that records the commands it receives. That
listener is `serving_valkey`. A test of INFO uses it too. It replies with the text of a server,
and the client's own parser turns that text into the mapping the test reads.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

import pytest
from fakeredis import FakeServer, FakeValkey

from devops_cli.valkey.client import ValkeyClient
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS


def valkey_client_on(server: FakeServer, *, password: str | None = None) -> ValkeyClient:
    """A `ValkeyClient` connected to an in-memory server.

    The pool is the fake's own, so the client's `password`, `db` and decoding arguments play no
    part.
    """
    pool = FakeValkey(
        server=server, password=password, decode_responses=True, encoding_errors="replace"
    ).connection_pool
    return ValkeyClient(host="127.0.0.1", connection_pool=pool)


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
) -> Iterator[tuple[int, list[list[str]]]]:
    """A loopback server that records the commands it receives and answers each from `replies`.

    `replies` maps an upper-case command name to its RESP reply; any other command is answered
    +OK. The yielded record is complete once the block exits, which waits for the client to close
    its connection. valkey-py announces its name and version with `CLIENT SETINFO` after it
    connects; the record leaves those out.
    """
    answers = replies or {}
    received: list[list[str]] = []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)

        def serve() -> None:
            connection, _ = listener.accept()
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
        yield listener.getsockname()[1], received
        server.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
