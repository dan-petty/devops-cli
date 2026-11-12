"""The network block of the dry-run tests: a dry run sends no request, not even to a fake (#412).

The floor of the suite already refuses each program but git, each connect to a host that is not
loopback and each DNS query (`tests/conftest.py`), so a dry-run test needs no block of its own for
them. A fake answers a request at its edge, such as the `web` transport or a server on a loopback
port that the test owns, and the floor does not see a request that reaches a fake. The
`refuse_requests` fixture refuses each socket connect and each request of an httpx2 client. It
records each one and fails the test at teardown, also when the code under test caught the
refusal.
"""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from typing import NoReturn

import httpx2
import pytest


@pytest.fixture
def refuse_requests(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Refuse and record each socket connect and each httpx2 request of the test."""
    reached: list[str] = []

    def refusing(edge: str) -> Callable[..., NoReturn]:
        def refuse(_client: object, target: object, *_args: object, **_kwargs: object) -> NoReturn:
            reached.append(f"{edge} {target}")
            raise AssertionError(f"A dry run made an external request: {edge} {target}")

        return refuse

    monkeypatch.setattr(socket.socket, "connect", refusing("connect to"))
    monkeypatch.setattr(httpx2.Client, "send", refusing("HTTP request"))
    monkeypatch.setattr(httpx2.AsyncClient, "send", refusing("HTTP request"))
    yield reached
    assert reached == [], f"A dry run made external requests: {reached}"
