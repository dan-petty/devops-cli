"""Security-related exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_SECURITY,
    CONST_EXIT_FAILURE,
    CONST_MSG_KEYRING_UNAVAILABLE,
    CONST_MSG_SSRF_RESOLVES_PRIVATE,
)
from devops_cli.exceptions.base import DevOpsCLIError


class SecurityError(DevOpsCLIError, ValueError):
    """Base exception for all security, policy, and egress violations."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_SECURITY,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=details)


class SSRFBlockedError(SecurityError):
    """Raised when an outbound HTTP request targets a private or forbidden network IP."""

    def __init__(
        self,
        target_url: str,
        *,
        reason: str = CONST_MSG_SSRF_RESOLVES_PRIVATE,
        details: dict[str, Any] | None = None,
    ) -> None:
        from urllib.parse import urlparse

        parsed = urlparse(target_url)
        safe_host = "<masked>" if parsed.hostname else "<invalid-target>"
        port_str = f":{parsed.port}" if parsed.port else ""
        scheme_str = f"{parsed.scheme}://" if parsed.scheme else ""
        safe_url = f"{scheme_str}{safe_host}{port_str}{parsed.path or ''}"
        msg = f"SSRF blocked: {safe_url} ({reason})"
        err_details: dict[str, Any] = {"target_url": target_url, "reason": reason}
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
        message: str = CONST_MSG_KEYRING_UNAVAILABLE,
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


class InsecureConfigError(SecurityError):
    """Raised when an unencrypted plaintext secret token is found in configuration files."""

    def __init__(
        self,
        option_key: str,
        reason: str = "Plaintext secret detected in config file",
        path: Any = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        path_str = str(path) if path else "config"
        msg = f"Insecure configuration ({option_key}) at {path_str}: {reason}"
        err_details = {"option_key": option_key, "reason": reason, "path": path_str}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            exit_code=126,
            error_code="E_INSECURE_CONFIG",
            details=err_details,
        )
