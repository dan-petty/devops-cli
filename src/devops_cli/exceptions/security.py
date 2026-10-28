"""Security-related exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_MSG_KEYRING_UNAVAILABLE,
    CONST_MSG_SSRF_RESOLVES_PRIVATE,
)
from devops_cli.exceptions.base import DevOpsCLIError


class SecurityError(DevOpsCLIError, ValueError):
    """Base exception for all security, policy, and egress violations."""

    error_code = "SECURITY_ERROR"


class SSRFBlockedError(SecurityError):
    """Raised when an outbound HTTP request targets a private or forbidden network IP."""

    error_code = "SSRF_BLOCKED"
    exit_code = 2

    def __init__(
        self,
        target_url: str,
        *,
        reason: str = CONST_MSG_SSRF_RESOLVES_PRIVATE,
        details: dict[str, Any] | None = None,
    ) -> None:
        import httpx2

        from devops_cli.security.sanitizer import mask_uri_credentials

        clean_target = mask_uri_credentials(target_url)
        if clean_target == "<masked-url>":
            msg = f"SSRF blocked: <masked-url> ({reason})"
        else:
            try:
                parsed = httpx2.URL(clean_target)
                scheme_str = f"{parsed.scheme}://" if parsed.scheme else ""
                port_str = f":{parsed.port}" if parsed.port is not None else ""
                path_str = parsed.path or ""
                safe_url = f"{scheme_str}<masked>{port_str}{path_str}"
                msg = f"SSRF blocked: {safe_url} ({reason})"
            except httpx2.InvalidURL:
                clean_target = "<masked-url>"
                msg = f"SSRF blocked: <masked-url> ({reason})"

        bounded_target = clean_target[:256]
        bounded_reason = str(reason)[:256]
        err_details: dict[str, Any] = {"target_url": bounded_target, "reason": bounded_reason}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            details=err_details,
        )
        self.details["target_url"] = bounded_target


class KeyringUnavailableError(SecurityError):
    """Raised when the OS Keyring service is unreachable or uninitialized."""

    error_code = "KEYRING_UNAVAILABLE"
    exit_code = 3

    def __init__(
        self,
        message: str = CONST_MSG_KEYRING_UNAVAILABLE,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            details=details,
        )
