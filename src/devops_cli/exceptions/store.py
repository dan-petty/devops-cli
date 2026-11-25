"""Content store exception definitions for devops-cli (#4761)."""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


class StoreError(DevOpsCLIError):
    """Raised when an S3 content store operation fails or a store request is refused."""

    error_code = "STORE_ERROR"

    def __init__(
        self,
        message: str,
        *,
        bucket: str | None = None,
        key: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        unreachable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.bucket = bucket
        self.key = key
        self.endpoint = endpoint
        self.status_code = status_code
        self.unreachable = unreachable
        err_details: dict[str, Any] = {}
        if bucket is not None:
            err_details["bucket"] = bucket
        if key is not None:
            err_details["key"] = key
        if endpoint is not None:
            err_details["endpoint"] = endpoint
        if status_code is not None:
            err_details["status_code"] = status_code
        if details:
            err_details.update(details)
        super().__init__(message, details=err_details)


class StoreImmutablePathError(StoreError):
    """Raised when publishing to an existing immutable store path without `--replace`."""

    error_code = "STORE_IMMUTABLE_PATH"
