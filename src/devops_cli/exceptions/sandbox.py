"""Workload sandbox domain exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


def _truncate_field(value: Any, max_len: int = 256) -> str:
    """Safely bound and truncate strings to avoid log bloat and injection."""
    text = str(value)
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


class SandboxError(DevOpsCLIError):
    """Base exception for workload sandbox lifecycle operations."""

    error_code = "SANDBOX_ERROR"

    def __init__(
        self,
        message: str,
        *,
        instance_id: str | None = None,
        container_id: str | None = None,
        image: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details: dict[str, Any] = {}
        if instance_id:
            err_details["instance_id"] = _truncate_field(instance_id)
        if container_id:
            err_details["container_id"] = _truncate_field(container_id)
        if image:
            err_details["image"] = _truncate_field(image)
        if details:
            for k, v in details.items():
                err_details[_truncate_field(k, 64)] = _truncate_field(v)
        super().__init__(
            message,
            exit_code=exit_code,
            details=err_details or None,
        )


class SandboxValidationError(SandboxError, ValueError):
    """Raised when sandbox configuration or directory mount paths violate security boundaries."""

    error_code = "SANDBOX_VALIDATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = dict(details) if details else {}
        if path:
            err_details["path"] = _truncate_field(path)
        super().__init__(
            message,
            details=err_details,
        )


class SandboxUnavailableError(SandboxError):
    """Raised when this host cannot start the sandbox of a review tool, so the tool does not run.

    The message is the cause: bubblewrap or prlimit is not installed, or the kernel refuses
    bubblewrap a user namespace. A scan reports the cause as a coverage gap.
    """

    error_code = "SANDBOX_UNAVAILABLE_ERROR"


class SandboxPortAllocationError(SandboxError, RuntimeError):
    """Raised when host port allocation encounters collisions or range exhaustion."""

    error_code = "SANDBOX_PORT_ALLOCATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        requested_port: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = dict(details) if details else {}
        if requested_port is not None:
            err_details["requested_port"] = requested_port
        super().__init__(
            message,
            details=err_details,
        )


class SandboxNotFoundError(SandboxError, KeyError):
    """Raised when requested sandbox instance or container cannot be found."""

    error_code = "SANDBOX_NOT_FOUND_ERROR"

    def __init__(
        self,
        message: str,
        *,
        identifier: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = dict(details) if details else {}
        if identifier:
            err_details["identifier"] = _truncate_field(identifier)
        super().__init__(
            message,
            details=err_details,
        )


__all__ = [
    "SandboxError",
    "SandboxNotFoundError",
    "SandboxPortAllocationError",
    "SandboxUnavailableError",
    "SandboxValidationError",
]
