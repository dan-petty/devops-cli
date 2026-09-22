"""Docker container domain exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_COSIGN,
    CONST_ERROR_CODE_COSIGN_VERIFY,
    CONST_ERROR_CODE_DOCKER_DAEMON_UNAVAILABLE,
    CONST_ERROR_CODE_DOCKER_ENGINE,
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


class DockerEngineError(DockerError):
    """Raised when a Docker Engine API call over the daemon socket fails."""

    def __init__(
        self,
        message: str,
        *,
        container_id: str | None = None,
        image: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_DOCKER_ENGINE,
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


class DockerDaemonUnavailableError(DockerEngineError):
    """Raised when the Docker daemon socket cannot be reached or negotiated."""

    def __init__(
        self,
        message: str,
        *,
        host: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_DOCKER_DAEMON_UNAVAILABLE,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"host": host}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=exit_code,
            error_code=error_code,
            details=err_details,
        )


class CosignError(DockerError):
    """Raised when Sigstore Cosign image signing fails."""

    def __init__(
        self,
        message: str,
        *,
        image: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_COSIGN,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            image=image,
            exit_code=exit_code,
            error_code=error_code,
            details=details,
        )


class CosignVerificationError(DockerError):
    """Raised when Sigstore Cosign signature or attestation verification fails."""

    def __init__(
        self,
        message: str,
        *,
        image: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_COSIGN_VERIFY,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            image=image,
            exit_code=exit_code,
            error_code=error_code,
            details=details,
        )


__all__ = [
    "CosignError",
    "CosignVerificationError",
    "DockerDaemonUnavailableError",
    "DockerEngineError",
    "DockerError",
    "DockerSandboxError",
]
