"""Unit tests for declarative @cli_command_handler decorator."""

from __future__ import annotations

import pytest
import typer

from devops_cli.core.command_decorator import cli_command_handler
from devops_cli.exceptions.base import DevOpsCLIError


def test_cli_command_handler_success() -> None:
    """Decorator should execute wrapped function and return result."""

    @cli_command_handler("test_cmd")
    def sample_command(x: int, y: int) -> int:
        return x + y

    res = sample_command(3, 4)
    assert res == 7


def test_cli_command_handler_handles_devops_cli_error() -> None:
    """Decorator should catch DevOpsCLIError, emit log and exit with error code."""

    @cli_command_handler("failing_cmd")
    def failing_command() -> None:
        raise DevOpsCLIError("Domain error occurred", error_code="ERR_DOMAIN", exit_code=42)

    with pytest.raises(typer.Exit) as exc_info:
        failing_command()

    assert exc_info.value.exit_code == 42
