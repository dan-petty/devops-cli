"""Validation-related exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_MSG_URL_INVALID,
)
from devops_cli.exceptions.base import DevOpsCLIError


class ValidationError(DevOpsCLIError, ValueError):
    """Base exception for user input and format validation failures."""

    error_code = "VALIDATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"field": field} if field else {}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class InvalidURLError(ValidationError):
    """Raised when an invalid URL or URI scheme is provided.

    The URL can hold userinfo and a path, so the error names its server as `server_label` does,
    by `host[:port]`, or as `unknown` when the text has no origin. It never holds the URL.
    """

    error_code = "INVALID_URL"

    def __init__(
        self,
        url: str,
        reason: str = CONST_MSG_URL_INVALID,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        from devops_cli.ai.benchmark.labels import server_label

        label = server_label(url)
        msg = f"Invalid URL '{label}': {reason}"
        err_details = {"url": label, "reason": reason}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            field="url",
            details=err_details,
        )
