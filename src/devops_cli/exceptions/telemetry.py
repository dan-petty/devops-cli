"""Telemetry and Logfire observability domain exceptions for devops-cli."""

from __future__ import annotations

from devops_cli.exceptions.base import DevOpsCLIError


class TelemetryError(DevOpsCLIError):
    """Base exception for telemetry, tracing, and metric collection errors."""

    error_code = "TELEMETRY_ERROR"

    def __init__(
        self,
        message: str = "Telemetry error encountered",
        exit_code: int | None = None,
    ) -> None:
        super().__init__(message=message, exit_code=exit_code)


class LogfireConfigurationError(TelemetryError):
    """Raised when Logfire configuration fails or credentials cannot be retrieved."""

    error_code = "LOGFIRE_CONFIG_ERROR"

    def __init__(
        self,
        message: str = "Logfire configuration failed",
        exit_code: int | None = None,
    ) -> None:
        super().__init__(message=message, exit_code=exit_code)


class OtlpExportError(TelemetryError):
    """Raised when the collector does not take an OTLP export, with the failure as its message."""

    def __init__(
        self,
        message: str = "The collector did not take the export",
        exit_code: int | None = None,
    ) -> None:
        super().__init__(message=message, exit_code=exit_code)


class OtlpProtocolError(TelemetryError, ValueError):
    """Raised when the OTLP protocol or endpoint asks for gRPC, which devops-cli does not send."""

    def __init__(
        self,
        message: str = "devops-cli sends OTLP over HTTP only",
        exit_code: int | None = None,
    ) -> None:
        super().__init__(message=message, exit_code=exit_code)


class ServiceStatusError(TelemetryError):
    """Raised when querying upstream published service status fails."""

    error_code = "SERVICE_STATUS_ERROR"

    def __init__(
        self,
        message: str = "Failed to query upstream service status",
        exit_code: int | None = None,
    ) -> None:
        super().__init__(message=message, exit_code=exit_code)
