"""Kubernetes domain exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_K8S,
    CONST_EXIT_FAILURE,
)
from devops_cli.exceptions.base import DevOpsCLIError


class KubernetesError(DevOpsCLIError):
    """Base exception for Kubernetes operations."""

    def __init__(
        self,
        message: str,
        *,
        context: str | None = None,
        namespace: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_K8S,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"context": context, "namespace": namespace}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class KubernetesContextError(KubernetesError, ValueError):
    """Raised when a Kubernetes context cannot be resolved or is invalid."""

    def __init__(
        self,
        message: str,
        *,
        context: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "K8S_CONTEXT_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            context=context,
            exit_code=exit_code,
            error_code=error_code,
            details=details,
        )


class ChaosExecutionError(KubernetesError, RuntimeError):
    """Raised when chaos engineering injection or validation fails."""

    def __init__(
        self,
        message: str,
        *,
        experiment_name: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "CHAOS_EXECUTION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"experiment_name": experiment_name}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=exit_code,
            error_code=error_code,
            details=err_details,
        )


class KubernetesDeployError(KubernetesError, RuntimeError):
    """Raised when deploying manifests or Helm charts fails."""

    def __init__(
        self,
        message: str,
        *,
        chart_or_manifest: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "K8S_DEPLOY_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"chart_or_manifest": chart_or_manifest}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=exit_code,
            error_code=error_code,
            details=err_details,
        )


__all__ = [
    "ChaosExecutionError",
    "KubernetesContextError",
    "KubernetesDeployError",
    "KubernetesError",
]
