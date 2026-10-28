"""HashiCorp Vault domain exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


class VaultError(DevOpsCLIError):
    """Base exception for HashiCorp Vault operations."""

    error_code = "VAULT_ERROR"

    def __init__(
        self,
        message: str,
        *,
        vault_addr: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"vault_addr": vault_addr}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class VaultKeyError(VaultError, KeyError):
    """Raised when a secret key or field is not found in Vault."""

    error_code = "VAULT_KEY_ERROR"

    def __init__(
        self,
        message: str,
        *,
        secret_path: str | None = None,
        key_name: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"secret_path": secret_path, "key_name": key_name}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class VaultConfigurationError(VaultError, ValueError):
    """Raised when Vault environment or connection settings are missing or invalid."""

    error_code = "VAULT_CONFIGURATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        config_key: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"config_key": config_key}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class VaultOperationError(VaultError, RuntimeError):
    """Raised when an API request to Vault fails or returns an error response."""

    error_code = "VAULT_OPERATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"status_code": status_code}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class VaultAuthenticationError(VaultError):
    """Raised when Vault issues or accepts no token: a failed login, none usable, or one refused.

    A refused token is one Vault answered with HTTP 401 or 403.
    """

    error_code = "VAULT_AUTH_ERROR"

    def __init__(
        self,
        message: str,
        *,
        vault_addr: str | None = None,
        method: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"method": method}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            vault_addr=vault_addr,
            exit_code=exit_code,
            details=err_details,
        )


class VaultLeaseError(VaultError):
    """Raised when a Vault lease, login or token call fails, with Vault's HTTP status.

    `status_code` is the status Vault answered with, or None when the call failed before that.
    """

    error_code = "VAULT_LEASE_ERROR"

    def __init__(
        self,
        message: str,
        *,
        vault_addr: str | None = None,
        lease_id: str | None = None,
        status_code: int | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        err_details: dict[str, Any] = {"lease_id": lease_id, "status_code": status_code}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            vault_addr=vault_addr,
            exit_code=exit_code,
            details=err_details,
        )


class VaultUnreachableError(VaultOperationError):
    """Raised when no reply came back from Vault: the connection failed or timed out."""


__all__ = [
    "VaultAuthenticationError",
    "VaultConfigurationError",
    "VaultError",
    "VaultKeyError",
    "VaultLeaseError",
    "VaultOperationError",
    "VaultUnreachableError",
]
