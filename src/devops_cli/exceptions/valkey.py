"""Valkey in-memory data store and caching domain exceptions."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_VALKEY,
    CONST_EXIT_FAILURE,
)
from devops_cli.exceptions.base import DevOpsCLIError


class ValkeyError(DevOpsCLIError):
    """Base exception for Valkey workstation and caching operations."""

    def __init__(
        self,
        message: str,
        *,
        host: str | None = None,
        port: int | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_VALKEY,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details: dict[str, Any] = {}
        if host:
            err_details["host"] = host
        if port:
            err_details["port"] = port
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class ValkeyConnectionError(ValkeyError, ConnectionError):
    """Raised when connection to Valkey instance fails, times out, or drops."""

    def __init__(
        self,
        message: str,
        *,
        host: str | None = None,
        port: int | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "VALKEY_CONNECTION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            host=host,
            port=port,
            exit_code=exit_code,
            error_code=error_code,
            details=details,
        )


class ValkeyAuthenticationError(ValkeyError, PermissionError):
    """Raised when Valkey password authentication fails."""

    def __init__(
        self,
        message: str,
        *,
        host: str | None = None,
        port: int | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "VALKEY_AUTHENTICATION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            host=host,
            port=port,
            exit_code=exit_code,
            error_code=error_code,
            details=details,
        )


class ValkeyCommandError(ValkeyError, RuntimeError):
    """Raised when a Valkey command execution returns an error from server."""

    def __init__(
        self,
        message: str,
        *,
        command: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "VALKEY_COMMAND_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"command": command} if command else {}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=exit_code,
            error_code=error_code,
            details=err_details,
        )


class ValkeyTimeoutError(ValkeyError, TimeoutError):
    """Raised when a Valkey socket operation exceeds timeout."""

    def __init__(
        self,
        message: str,
        *,
        timeout_seconds: float | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "VALKEY_TIMEOUT_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"timeout_seconds": timeout_seconds} if timeout_seconds else {}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=exit_code,
            error_code=error_code,
            details=err_details,
        )
