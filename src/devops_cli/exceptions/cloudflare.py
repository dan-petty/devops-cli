"""Domain exceptions for Cloudflare API and tunnel routing."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import CONST_EXIT_FAILURE
from devops_cli.exceptions.base import DevOpsCLIError


class CloudflareError(DevOpsCLIError):
    """Base exception for Cloudflare domain errors."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "CLOUDFLARE_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=details)


class CloudflareAuthError(CloudflareError):
    """Raised when Cloudflare authentication or token verification fails."""

    def __init__(
        self,
        message: str = "Cloudflare API token is invalid or unauthorized.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code="CLOUDFLARE_AUTH_ERROR", details=details)


class CloudflareAPIError(CloudflareError):
    """Raised when a Cloudflare API call returns an error response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        payload = dict(details) if details else {}
        if status_code is not None:
            payload["status_code"] = status_code
        super().__init__(message, error_code="CLOUDFLARE_API_ERROR", details=payload)
