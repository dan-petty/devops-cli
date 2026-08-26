"""Security-related exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


class SecurityError(DevOpsCLIError, ValueError):
    """Base exception for all security, policy, and egress violations."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int = 1,
        error_code: str = "SECURITY_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=details)


class SSRFBlockedError(SecurityError):
    """Raised when an outbound HTTP request targets a private or forbidden network IP."""

    def __init__(
        self,
        target_url: str,
        *,
        reason: str = "Target resolves to a private or loopback network endpoint",
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = f"SSRF blocked: {target_url} ({reason})"
        err_details = {"target_url": target_url, "reason": reason}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            exit_code=2,
            error_code="SSRF_BLOCKED",
            details=err_details,
        )


class KeyringUnavailableError(SecurityError):
    """Raised when the OS Keyring service is unreachable or uninitialized."""

    def __init__(
        self,
        message: str = "OS Keyring service is unavailable; run in headless CI mode",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            exit_code=3,
            error_code="KEYRING_UNAVAILABLE",
            details=details,
        )


class SecretExposureError(SecurityError):
    """Raised when an unmasked credential or private key is detected in uncommitted diffs."""

    def __init__(
        self,
        secret_type: str,
        location: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = f"Secret exposure detected ({secret_type}) at {location}"
        err_details = {"secret_type": secret_type, "location": location}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            exit_code=4,
            error_code="SECRET_EXPOSURE_DETECTED",
            details=err_details,
        )
