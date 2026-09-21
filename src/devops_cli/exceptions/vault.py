"""HashiCorp Vault domain exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_VAULT,
    CONST_ERROR_CODE_VAULT_AUTH,
    CONST_ERROR_CODE_VAULT_LEASE,
    CONST_EXIT_FAILURE,
)
from devops_cli.exceptions.base import DevOpsCLIError


class VaultError(DevOpsCLIError):
    """Base exception for HashiCorp Vault operations."""

    def __init__(
        self,
        message: str,
        *,
        vault_addr: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_VAULT,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"vault_addr": vault_addr}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class VaultKeyError(VaultError, KeyError):
    """Raised when a secret key or field is not found in Vault."""

    def __init__(
        self,
        message: str,
        *,
        secret_path: str | None = None,
        key_name: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "VAULT_KEY_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"secret_path": secret_path, "key_name": key_name}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class VaultConfigurationError(VaultError, ValueError):
    """Raised when Vault environment or connection settings are missing or invalid."""

    def __init__(
        self,
        message: str,
        *,
        config_key: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "VAULT_CONFIGURATION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"config_key": config_key}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class VaultOperationError(VaultError, RuntimeError):
    """Raised when an API request to Vault fails or returns an error response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "VAULT_OPERATION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"status_code": status_code}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class VaultAuthenticationError(VaultError):
    """Raised when a Vault login method fails to issue a client token."""

    def __init__(
        self,
        message: str,
        *,
        vault_addr: str | None = None,
        method: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_VAULT_AUTH,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"method": method}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            vault_addr=vault_addr,
            exit_code=exit_code,
            error_code=error_code,
            details=err_details,
        )


class VaultLeaseError(VaultError):
    """Raised when a dynamic secret lease cannot be renewed or revoked."""

    def __init__(
        self,
        message: str,
        *,
        vault_addr: str | None = None,
        lease_id: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_VAULT_LEASE,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"lease_id": lease_id}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            vault_addr=vault_addr,
            exit_code=exit_code,
            error_code=error_code,
            details=err_details,
        )


__all__ = [
    "VaultAuthenticationError",
    "VaultConfigurationError",
    "VaultError",
    "VaultKeyError",
    "VaultLeaseError",
    "VaultOperationError",
]
