"""Argo GitOps and progressive delivery domain exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


class ArgoError(DevOpsCLIError):
    """Base exception for Argo CD, Rollouts, and Workflows operations."""

    error_code = "ARGO_ERROR"

    def __init__(
        self,
        message: str,
        *,
        resource: str | None = None,
        namespace: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"resource": resource, "namespace": namespace}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class ArgoResourceNotFoundError(ArgoError):
    """Raised when an Argo custom resource does not exist in the target cluster."""

    error_code = "ARGO_RESOURCE_NOT_FOUND"


__all__ = [
    "ArgoError",
    "ArgoResourceNotFoundError",
]
