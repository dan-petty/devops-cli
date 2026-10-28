"""Docker container domain exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


class DockerError(DevOpsCLIError):
    """Base exception for Docker operations."""

    error_code = "DOCKER_ERROR"

    def __init__(
        self,
        message: str,
        *,
        container_id: str | None = None,
        image: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"container_id": container_id, "image": image}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class DockerSandboxError(DockerError, ValueError):
    """Raised when docker sandbox execution, container creation, or termination fails."""

    error_code = "DOCKER_SANDBOX_ERROR"


class DockerEngineError(DockerError):
    """Raised when a Docker Engine API call over the daemon socket fails."""

    error_code = "DOCKER_ENGINE_ERROR"


class DockerDaemonUnavailableError(DockerEngineError):
    """Raised when the Docker daemon socket cannot be reached or negotiated."""

    error_code = "DOCKER_DAEMON_UNAVAILABLE"

    def __init__(
        self,
        message: str,
        *,
        host: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"host": host}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=exit_code,
            details=err_details,
        )


class CosignError(DockerError):
    """Raised when Sigstore Cosign image signing fails."""

    error_code = "COSIGN_ERROR"


class CosignVerificationError(DockerError):
    """Raised when Sigstore Cosign signature or attestation verification fails."""

    error_code = "COSIGN_VERIFICATION_FAILED"


__all__ = [
    "CosignError",
    "CosignVerificationError",
    "DockerDaemonUnavailableError",
    "DockerEngineError",
    "DockerError",
    "DockerSandboxError",
]
