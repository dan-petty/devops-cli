"""The TCP probe of a host and port, answered by a test: the `tcp_probe` fixture.

Code that asks whether an address accepts connections calls `socket.create_connection` and
reads nothing from the socket. That stdlib call is the edge, so the fixture replaces it, as
`docs/TESTING.md` allows for a stdlib edge that no seam reaches. A probe succeeds only for an
address a test made listen, and the fixture records each probe. Names are generic.
"""

from __future__ import annotations

import errno
import os
import socket
from collections.abc import Callable
from types import TracebackType
from typing import Any

import pytest

Address = tuple[str, int]


class _Connection:
    """The socket that a successful probe returns: it holds nothing and closes at once."""

    def __enter__(self) -> _Connection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def close(self) -> None:
        """Close the stand-in socket."""


class TcpProbe:
    """Answers each `socket.create_connection` probe: refused unless a test made it listen."""

    def __init__(self) -> None:
        self.probed: list[Address] = []
        self._listening: list[Callable[[str, int], bool]] = []

    def listen(self, host: str, port: int) -> None:
        """Make `host:port` accept connections."""
        self.listen_where(
            lambda probed_host, probed_port: (probed_host, probed_port) == (host, port)
        )

    def listen_where(self, accepts: Callable[[str, int], bool]) -> None:
        """Make every address for which `accepts(host, port)` is true accept connections."""
        self._listening.append(accepts)

    def refuse_all(self) -> None:
        """Make every address refuse connections again."""
        self._listening.clear()

    def create_connection(self, address: Address, *args: Any, **kwargs: Any) -> _Connection:
        """Record the probe and accept it, or refuse it as a closed port does."""
        host, port = address
        self.probed.append((host, port))
        if any(accepts(host, port) for accepts in self._listening):
            return _Connection()
        raise ConnectionRefusedError(errno.ECONNREFUSED, os.strerror(errno.ECONNREFUSED))


@pytest.fixture
def tcp_probe(monkeypatch: pytest.MonkeyPatch) -> TcpProbe:
    """Refuse every TCP probe, as a workstation with no port-forward running does, until a test
    makes an address listen."""
    fake = TcpProbe()
    monkeypatch.setattr(socket, "create_connection", fake.create_connection)
    return fake
