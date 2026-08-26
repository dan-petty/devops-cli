"""Base domain exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import CONST_ERROR_CODE_DEVOPS_CLI, CONST_EXIT_FAILURE


class DevOpsCLIError(Exception):
    """Root base exception for all domain-specific errors in devops-cli.

    Attributes:
        message: Human-readable error explanation.
        exit_code: POSIX process exit status code (defaults to 1).
        error_code: Canonical machine-readable identifier string.
        details: Optional structured dictionary containing contextual debug data.
    """

    def __init__(
        self,
        message: str,
        *,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_DEVOPS_CLI,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.error_code = error_code
        self.details = details or {}

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert exception attributes into a serialized dictionary representation."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "exit_code": self.exit_code,
            "details": self.details,
        }
