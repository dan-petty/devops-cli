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
arguments send and read binds a loopback listener that records the commands it receives.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fakeredis import FakeServer, FakeValkey

from devops_cli.valkey.client import ValkeyClient


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
