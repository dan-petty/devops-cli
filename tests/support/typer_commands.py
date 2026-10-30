"""Build the click command of a Typer app once for each state of it, not once for each invocation (#2699).

`typer.testing.CliRunner.invoke(app, ...)` calls `typer.main.get_command(app)` on each call, which
reads the signature of every command function of the app to build its parameters. For the `devops`
app that is 4,800 commands and 100 ms of CPU for each invocation: in a sample of 1,040 tests, 317
invocations took 13% of the time of the run. The command that `get_command` returns holds no state
of a call, so the first build of an app serves every later call while the app is unchanged.

A test adds a command to `devops_cli.main.app` and removes it after (the in-process dispatch tests
do). The cache is therefore kept by the commands and groups the app has registered, and holds them,
so an object that a test drops never gives its address to the next one. The app is held weakly, so
an app that a test builds for itself goes with the test.
"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

_COMMANDS: weakref.WeakKeyDictionary[Any, dict[tuple[Any, ...], tuple[Any, Any]]] = (
    weakref.WeakKeyDictionary()
)


def _registered(app: Any) -> tuple[Any, ...]:
    """What the app has registered, as objects: the commands, the groups and the callback."""
    return (*app.registered_commands, *app.registered_groups, app.registered_callback)


@pytest.fixture(autouse=True, scope="session")
def cached_typer_commands() -> Iterator[None]:
    """Make `typer.testing.CliRunner.invoke` take the click command of an app from the cache."""
    import typer.testing
    from typer.main import get_command

    def cached(app: Any) -> Any:
        state = _registered(app)
        key = tuple(map(id, state))
        entries = _COMMANDS.setdefault(app, {})
        if key not in entries:
            entries[key] = (get_command(app), state)
        return entries[key][0]

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(typer.testing, "_get_command", cached)
        yield
