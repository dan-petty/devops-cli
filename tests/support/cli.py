"""The shared CLI command runner fixture (#1310)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pytest

_TERMINAL_ENV = {"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"}


@pytest.fixture
def cli() -> Callable[..., Any]:
    """Run `devops <args>` in process through `devops_cli.main.app` with the floor's terminal settings (#1310)."""
    from typer.testing import CliRunner

    from devops_cli.main import app

    runner = CliRunner(env=_TERMINAL_ENV)

    def invoke(
        *args: str | Sequence[str],
        input: str | bytes | None = None,
        env: Mapping[str, str | None] | None = None,
        catch_exceptions: bool = True,
    ) -> Any:
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            argv = [str(item) for item in args[0]]
        else:
            argv = [str(item) for item in args]
        merged_env = {**_TERMINAL_ENV, **(env or {})}
        return runner.invoke(
            app,
            argv,
            input=input,
            env=merged_env,
            catch_exceptions=catch_exceptions,
        )

    return invoke
