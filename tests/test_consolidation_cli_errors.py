"""Unit tests for CLI command error boundary and decorator (TDD Specification)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import typer

from devops_cli.core.command_decorator import cli_command_handler
from devops_cli.exceptions.base import DevOpsCLIError


class CustomDomainError(DevOpsCLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, error_code="CONST_ERROR_CODE_CUSTOM_DOMAIN", exit_code=42)


def test_cli_command_handler_success() -> None:
    """Successful command execution returns value cleanly."""

    @cli_command_handler("test.success")
    def sample_cmd(x: int) -> int:
        return x * 2

    assert sample_cmd(21) == 42


def test_cli_command_handler_catches_devops_cli_error() -> None:
    """Catches DevOpsCLIError, prints clean message, and raises typer.Exit with domain exit_code."""

    @cli_command_handler("test.domain_error")
    def failing_cmd() -> None:
        raise CustomDomainError("Action failed due to invalid state")

    with patch("devops_cli.core.command_decorator.print_error") as mock_print:
        with pytest.raises(typer.Exit) as exc_info:
            failing_cmd()
        assert exc_info.value.exit_code == 42
        mock_print.assert_called_once()
        msg = mock_print.call_args[0][0]
        assert "Action failed due to invalid state" in msg


def test_cli_command_handler_allows_typer_exit_passthrough() -> None:
    """Existing typer.Exit raises directly without double wrapping."""

    @cli_command_handler("test.exit")
    def exiting_cmd() -> None:
        raise typer.Exit(code=2)

    with pytest.raises(typer.Exit) as exc_info:
        exiting_cmd()
    assert exc_info.value.exit_code == 2
