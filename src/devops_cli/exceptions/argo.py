"""Argo GitOps and progressive delivery domain exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_ARGO,
    CONST_ERROR_CODE_ARGO_RESOURCE_NOT_FOUND,
    CONST_EXIT_FAILURE,
)
from devops_cli.exceptions.base import DevOpsCLIError


class ArgoError(DevOpsCLIError):
    """Base exception for Argo CD, Rollouts, and Workflows operations."""

    def __init__(
        self,
        message: str,
        *,
        resource: str | None = None,
        namespace: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_ARGO,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"resource": resource, "namespace": namespace}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class ArgoResourceNotFoundError(ArgoError):
    """Raised when an Argo custom resource does not exist in the target cluster."""

    def __init__(
        self,
        message: str,
        *,
        resource: str | None = None,
        namespace: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_ARGO_RESOURCE_NOT_FOUND,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            resource=resource,
            namespace=namespace,
            exit_code=exit_code,
            error_code=error_code,
            details=details,
        )


__all__ = [
    "ArgoError",
    "ArgoResourceNotFoundError",
]
