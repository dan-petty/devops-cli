"""Domain exceptions for Cloudflare API and tunnel routing."""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


class CloudflareError(DevOpsCLIError):
    """Base exception for Cloudflare domain errors."""

    error_code = "CLOUDFLARE_ERROR"


class CloudflareAuthError(CloudflareError):
    """Raised when Cloudflare authentication or token verification fails."""

    error_code = "CLOUDFLARE_AUTH_ERROR"

    def __init__(
        self,
        message: str = "Cloudflare API token is invalid or unauthorized.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class CloudflareAPIError(CloudflareError):
    """Raised when a Cloudflare API call returns an error response."""

    error_code = "CLOUDFLARE_API_ERROR"

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
        super().__init__(message, details=payload)
