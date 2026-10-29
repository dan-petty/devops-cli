"""Kubernetes domain exception definitions for devops-cli."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


class KubernetesError(DevOpsCLIError):
    """Base exception for Kubernetes operations."""

    error_code = "K8S_ERROR"

    def __init__(
        self,
        message: str,
        *,
        context: str | None = None,
        namespace: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"context": context, "namespace": namespace}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class KubernetesContextError(KubernetesError, ValueError):
    """Raised when a Kubernetes context cannot be resolved or is invalid."""

    error_code = "K8S_CONTEXT_ERROR"


class KubernetesTunnelError(KubernetesError):
    """Raised when `devops k8s tunnel` cannot start, find or stop its forward (#1641)."""

    error_code = "K8S_TUNNEL_ERROR"


class ImagePinError(KubernetesError):
    """Raised when an image that an Argo CD Application pins does not resolve in its registry, or an
    Application does not render (#1994)."""

    error_code = "K8S_IMAGE_PIN_ERROR"


class ArgoCDGateError(KubernetesError):
    """Raised when an Argo CD application fails offline build, value, or placeholder validation (#1343)."""

    error_code = "ARGOCD_GATE_ERROR"

    def __init__(
        self,
        message: str,
        *,
        failures: dict[str, list[str]] | None = None,
        context: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = dict(details or {})
        if failures:
            err_details["failures"] = failures
        super().__init__(
            message,
            context=context,
            exit_code=exit_code,
            details=err_details,
        )
        self.failures: dict[str, list[str]] = failures or {}


class ChaosExecutionError(KubernetesError, RuntimeError):
    """Raised when chaos engineering injection or validation fails."""

    error_code = "CHAOS_EXECUTION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        experiment_name: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"experiment_name": experiment_name}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=exit_code,
            details=err_details,
        )


class KubernetesDeployError(KubernetesError, RuntimeError):
    """Raised when deploying manifests or Helm charts fails."""

    error_code = "K8S_DEPLOY_ERROR"

    def __init__(
        self,
        message: str,
        *,
        chart_or_manifest: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"chart_or_manifest": chart_or_manifest}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=exit_code,
            details=err_details,
        )


class KubernetesLoggingError(KubernetesError, RuntimeError):
    """Raised when querying cluster logs or Loki fails."""

    error_code = "K8S_LOGGING_ERROR"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        query: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.query = query
        err_details = {"status_code": status_code, "query": query}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=exit_code,
            details=err_details,
        )


class ClusterSecretPushError(KubernetesError, RuntimeError):
    """Raised when cluster Secrets cannot be pushed from the keyring; nothing was written."""

    error_code = "K8S_SECRET_PUSH_ERROR"


class ClusterSecretWriteError(ClusterSecretPushError):
    """Raised when writing a planned push fails part-way; `completed` names what was written."""

    def __init__(self, message: str, *, completed: tuple[str, ...] = ()) -> None:
        super().__init__(message, details={"completed": list(completed)})
        self.completed = completed


class StackCredentialError(KubernetesError, RuntimeError):
    """Raised when a stack credential cannot be read, checked, minted, revoked or stored (#2156).

    The message gives the cause: the HTTP status or request error of the service, the kubectl
    error, or the keyring error.
    """

    error_code = "K8S_STACK_CREDENTIAL_ERROR"


class ClusterJobError(KubernetesError, RuntimeError):
    """Raised when a devops-cli Job cannot be created or followed in the cluster."""

    error_code = "K8S_CLUSTER_JOB_ERROR"


class VolumeReclaimError(KubernetesError, RuntimeError):
    """Raised when volume reclaim fails or is refused due to active claims or mounts."""

    error_code = "K8S_VOLUME_RECLAIM_ERROR"

    def __init__(
        self,
        message: str,
        *,
        volume: str | None = None,
        reason: str | None = None,
        context: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"volume": volume, "reason": reason}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            context=context,
            exit_code=exit_code,
            details=err_details,
        )


class DoctorCheckError(KubernetesError, RuntimeError):
    """Raised inside `devops k8s doctor --stack` when one check fails; the message is its reason.

    The doctor reports the reason as the result of that check and goes on to the next check, so
    the message never holds a secret value.
    """

    error_code = "K8S_DOCTOR_CHECK_FAILED"


class VolumeMoveError(KubernetesError, RuntimeError):
    """Raised when a volume move fails before the old claim is deleted; it undid its own steps.

    `undone` names the steps the undo ran, in order, and `undo_failures` each one that failed.
    """

    error_code = "K8S_VOLUME_MOVE_FAILED"

    def __init__(
        self,
        message: str,
        *,
        undone: tuple[str, ...] = (),
        undo_failures: tuple[str, ...] = (),
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details: dict[str, Any] = {
            "undone": list(undone),
            "undo_failures": list(undo_failures),
        }
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)
        self.undone = undone
        self.undo_failures = undo_failures


class VolumeMoveRefusedError(VolumeMoveError):
    """Raised when a volume move cannot start safely; it changed nothing."""

    error_code = "K8S_VOLUME_MOVE_REFUSED"

    def __init__(self, message: str, *, problems: tuple[str, ...] = ()) -> None:
        super().__init__(
            message,
            details={"problems": list(problems)},
        )
        self.problems = problems


class VolumeMoveStrandedError(VolumeMoveError):
    """Raised when a volume move fails after the old claim was deleted; Argo CD stays paused.

    A self-heal would make an empty claim, so the move resumes nothing. `saved_claim` is the
    deleted claim as it was read, and `remaining` names the steps that did not run.
    """

    error_code = "K8S_VOLUME_MOVE_STRANDED"

    def __init__(
        self,
        message: str,
        *,
        saved_claim: Path,
        paused: tuple[str, ...],
        remaining: tuple[str, ...],
        old_volume: str,
        new_volume: str,
    ) -> None:
        super().__init__(
            message,
            details={
                "saved_claim": str(saved_claim),
                "paused": list(paused),
                "remaining": list(remaining),
                "old_volume": old_volume,
                "new_volume": new_volume,
            },
        )
        self.saved_claim = saved_claim
        self.paused = paused
        self.remaining = remaining
        self.old_volume = old_volume
        self.new_volume = new_volume


__all__ = [
    "ArgoCDGateError",
    "ChaosExecutionError",
    "ClusterJobError",
    "ClusterSecretPushError",
    "ClusterSecretWriteError",
    "DoctorCheckError",
    "KubernetesContextError",
    "KubernetesDeployError",
    "KubernetesError",
    "KubernetesLoggingError",
    "StackCredentialError",
    "VolumeMoveError",
    "VolumeMoveRefusedError",
    "VolumeMoveStrandedError",
    "VolumeReclaimError",
]
