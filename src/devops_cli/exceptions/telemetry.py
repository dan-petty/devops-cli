"""Telemetry and Logfire observability domain exceptions for devops-cli."""

from __future__ import annotations

from devops_cli.config.constants import (
    CONST_ERROR_CODE_LOGFIRE,
    CONST_ERROR_CODE_TELEMETRY,
)
from devops_cli.exceptions.base import DevOpsCLIError


class TelemetryError(DevOpsCLIError):
    """Base exception for telemetry, tracing, and metric collection errors."""

    def __init__(
        self,
        message: str = "Telemetry error encountered",
        error_code: str = CONST_ERROR_CODE_TELEMETRY,
        exit_code: int = 1,
    ) -> None:
        super().__init__(message=message, error_code=error_code, exit_code=exit_code)


class LogfireConfigurationError(TelemetryError):
    """Raised when Logfire configuration fails or credentials cannot be retrieved."""

    def __init__(
        self,
        message: str = "Logfire configuration failed",
        error_code: str = CONST_ERROR_CODE_LOGFIRE,
        exit_code: int = 1,
    ) -> None:
        super().__init__(message=message, error_code=error_code, exit_code=exit_code)
