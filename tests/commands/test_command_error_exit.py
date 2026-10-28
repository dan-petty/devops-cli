"""Verify that a command reports a `DevOpsCLIError` through the one exit seam of `new_typer()` (#2487)."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterator

import pytest
import typer
from typer.testing import CliRunner

from devops_cli.core.cli import OTelTyper, new_typer
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.main import _COMMAND_SPECS

# Rich reads `[bold]` as markup. Printed as text, the message shows the brackets.
_MESSAGE = "the [bold]token[/bold] was refused"


class _Refused(DevOpsCLIError):
    """An error with an exit status of its own, as a domain error has."""


def _app_with_a_failing_command() -> OTelTyper:
    app = new_typer()

    @app.command("refuse")
    def refuse() -> None:
        raise _Refused(_MESSAGE, exit_code=7)

    @app.command("other")
    def other() -> None:
        """A second command, so that Typer keeps the command names."""

    return app


def _app_with_a_failing_callback() -> OTelTyper:
    app = new_typer()

    @app.callback(invoke_without_command=True)
    def run() -> None:
        raise _Refused(_MESSAGE, exit_code=7)

    return app


@pytest.mark.parametrize(
    ("make_app", "args"),
    [(_app_with_a_failing_command, ["refuse"]), (_app_with_a_failing_callback, [])],
    ids=["command", "callback"],
)
def test_a_devops_error_ends_the_command_with_one_line_and_its_exit_status(
    make_app: Callable[[], OTelTyper], args: list[str]
) -> None:
    """A command or a callback that runs as a command reports the error in one line, with its
    markup as text, and exits with the error's status, not with a traceback and status 1."""
    result = CliRunner().invoke(make_app(), args)

    lines = [line for line in result.output.splitlines() if line.strip()]
    assert (
        result.exit_code,
        type(result.exception),
        len(lines),
        _MESSAGE in result.output,
        "Traceback" in result.output,
    ) == (7, SystemExit, 1, True, False)


def _apps(app: typer.Typer) -> Iterator[typer.Typer]:
    yield app
    for group in app.registered_groups:
        if group.typer_instance is not None:
            yield from _apps(group.typer_instance)


def test_every_command_app_passes_its_commands_through_the_exit_seam() -> None:
    """Only an `OTelTyper` app wraps its commands in the seam, so no command app is a plain
    `typer.Typer`."""
    plain = sorted(
        f"{name}: {type(app).__name__}"
        for name, (module_path, _) in _COMMAND_SPECS.items()
        for app in _apps(importlib.import_module(module_path).app)
        if not isinstance(app, OTelTyper)
    )

    assert plain == []
