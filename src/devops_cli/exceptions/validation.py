"""Validation-related exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_VALIDATION,
    CONST_EXIT_FAILURE,
    CONST_MSG_URL_INVALID,
)
from devops_cli.exceptions.base import DevOpsCLIError


class ValidationError(DevOpsCLIError, ValueError):
    """Base exception for user input and format validation failures."""

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_VALIDATION,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"field": field} if field else {}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class InvalidURLError(ValidationError):
    """Raised when an invalid URL or URI scheme is provided."""

    def __init__(
        self,
        url: str,
        reason: str = CONST_MSG_URL_INVALID,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = f"Invalid URL '{url}': {reason}"
        err_details = {"url": url, "reason": reason}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            field="url",
            exit_code=CONST_EXIT_FAILURE,
            error_code="INVALID_URL",
            details=err_details,
        )


class InvalidVersionError(ValidationError):
    """Raised when a semantic version string cannot be parsed."""

    def __init__(
        self,
        version: str,
        tool_name: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        prefix = f"Invalid {tool_name} version string" if tool_name else "Invalid version string"
        msg = f"{prefix}: {version!r}"
        err_details = {"version": version, "tool_name": tool_name}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            field="version",
            exit_code=1,
            error_code="INVALID_VERSION",
            details=err_details,
        )
