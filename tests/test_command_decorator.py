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

    @cli_command_handler("failing_cmd", record_metrics=False)
    def failing_command() -> None:
        raise DevOpsCLIError("Domain error occurred", error_code="ERR_DOMAIN", exit_code=42)

    with pytest.raises(typer.Exit) as exc_info:
        failing_command()

    assert exc_info.value.exit_code == 42


def test_cli_command_handler_typer_exit_and_generic_exception() -> None:
    """Decorator should pass through typer.Exit and record metrics on generic exceptions."""

    # 1. typer.Exit passthrough
    @cli_command_handler("exit_cmd")
    def exit_command() -> None:
        raise typer.Exit(code=2)

    with pytest.raises(typer.Exit) as exc_info:
        exit_command()
    assert exc_info.value.exit_code == 2

    # 2. Generic Exception handling & metric recording
    @cli_command_handler("generic_err_cmd", record_metrics=True)
    def generic_err_command() -> None:
        raise ValueError("Something unexpected")

    with pytest.raises(ValueError):
        generic_err_command()

    # 3. Success with record_metrics=False
    @cli_command_handler("no_metrics_cmd", record_metrics=False)
    def no_metrics_command() -> str:
        return "ok"

    assert no_metrics_command() == "ok"
