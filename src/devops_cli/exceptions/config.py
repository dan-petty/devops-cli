"""Configuration exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


class ConfigurationError(DevOpsCLIError, ValueError):
    """Base exception for configuration loading, validation, and serialization errors."""

    error_code = "CONFIGURATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        key: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.key = key
        err_details = {"key": key} if key else {}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)
