"""The server start edge's fake (#3885).

`FakeServerStarter` is a `ServerStarter` (`devops_cli.server.start`) for a test of `devops serve`:
it records each `StartCall`, and when the call sets `factory` it builds the app from the target and
keeps it in `apps`, as uvicorn does. So the app exists only inside the start that the command made,
and a case that reads it asserts what the command asked for, never a factory that it called itself.

A test installs the fake with `install_server_starter`, and the reset of the test floor removes it
(`tests/conftest.py`). The `devops_cli.server.start` names are imported in the function that uses
them: the fail-to-pass replay runs a new test on the base tree, which holds no such module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

    from devops_cli.server.start import StartCall


class FakeServerStarter:
    """A `ServerStarter` that records each start and builds the app from a factory as uvicorn."""

    def __init__(self) -> None:
        self.calls: list[StartCall] = []
        self.apps: list[Any] = []

    def start(self, target: Any, /, **options: Any) -> None:
        """Record one start, and build the app from the target when the call sets `factory`."""
        from devops_cli.server.start import StartCall

        call = StartCall(target, dict(options))
        self.calls.append(call)
        if call.factory:
            self.apps.append(target())


@pytest.fixture
def server_starter() -> Iterator[FakeServerStarter]:
    """The server of `devops serve` started through a `FakeServerStarter` the test reads.

    `install_server_starter` puts the fake in place of `UvicornStarter`, and `remove_server_starter`
    gives the real starter back at teardown.
    """
    from devops_cli.server.start import install_server_starter, remove_server_starter

    fake = FakeServerStarter()
    install_server_starter(fake)
    yield fake
    remove_server_starter()
