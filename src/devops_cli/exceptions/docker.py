"""Docker container domain exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_DOCKER_SANDBOX,
    CONST_EXIT_FAILURE,
)
from devops_cli.exceptions.base import DevOpsCLIError


class DockerError(DevOpsCLIError):
    """Base exception for Docker operations."""

    def __init__(
        self,
        message: str,
        *,
        container_id: str | None = None,
        image: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "DOCKER_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"container_id": container_id, "image": image}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class DockerSandboxError(DockerError, ValueError):
    """Raised when docker sandbox execution, container creation, or termination fails."""

    def __init__(
        self,
        message: str,
        *,
        container_id: str | None = None,
        image: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_DOCKER_SANDBOX,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            container_id=container_id,
            image=image,
            exit_code=exit_code,
            error_code=error_code,
            details=details,
        )


__all__ = [
    "DockerError",
    "DockerSandboxError",
]
