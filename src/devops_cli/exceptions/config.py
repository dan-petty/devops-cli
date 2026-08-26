"""Configuration exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


class ConfigurationError(DevOpsCLIError, ValueError):
    """Base exception for configuration loading, validation, and serialization errors."""

    def __init__(
        self,
        message: str,
        *,
        key: str | None = None,
        exit_code: int = 1,
        error_code: str = "CONFIGURATION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"key": key} if key else {}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)
