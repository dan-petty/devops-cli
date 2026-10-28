"""Valkey in-memory data store and caching domain exceptions."""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


class ValkeyError(DevOpsCLIError):
    """Base exception for Valkey workstation and caching operations."""

    error_code = "VALKEY_ERROR"

    def __init__(
        self,
        message: str,
        *,
        host: str | None = None,
        port: int | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details: dict[str, Any] = {}
        if host:
            err_details["host"] = host
        if port:
            err_details["port"] = port
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class ValkeyConnectionError(ValkeyError, ConnectionError):
    """Raised when connection to Valkey instance fails, times out, or drops."""

    error_code = "VALKEY_CONNECTION_ERROR"


class ValkeyAuthenticationError(ValkeyError, PermissionError):
    """Raised when Valkey password authentication fails."""

    error_code = "VALKEY_AUTHENTICATION_ERROR"


class ValkeyCommandError(ValkeyError, RuntimeError):
    """Raised when a Valkey command execution returns an error from server."""

    error_code = "VALKEY_COMMAND_ERROR"

    def __init__(
        self,
        message: str,
        *,
        command: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"command": command} if command else {}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=exit_code,
            details=err_details,
        )


class ValkeyTimeoutError(ValkeyError, TimeoutError):
    """Raised when a Valkey socket operation exceeds timeout."""

    error_code = "VALKEY_TIMEOUT_ERROR"

    def __init__(
        self,
        message: str,
        *,
        timeout_seconds: float | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"timeout_seconds": timeout_seconds} if timeout_seconds else {}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=exit_code,
            details=err_details,
        )
