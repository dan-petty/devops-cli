"""Native Argo custom resource engine operating directly on the Kubernetes API.

Replaces `argocd`, `argo`, `kubectl`, and `kubectl-argo-rollouts` binary invocations
with in-process `CustomObjectsApi` calls, so no external CLI prerequisites are needed
on CI runners or developer workstations.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from devops_cli.config.constants import (
    CONST_ARGO_API_GROUP,
    CONST_ARGO_API_VERSION,
    CONST_ARGO_PLURAL_ANALYSIS_RUNS,
    CONST_ARGO_PLURAL_APPLICATION_SETS,
    CONST_ARGO_PLURAL_APPLICATIONS,
    CONST_ARGO_PLURAL_ROLLOUTS,
    CONST_ARGO_PLURAL_WORKFLOWS,
    CONST_ROLLOUT_FIELD_ABORT,
    CONST_ROLLOUT_FIELD_CONTROLLER_PAUSE,
    CONST_ROLLOUT_FIELD_PAUSE_CONDITIONS,
    CONST_ROLLOUT_FIELD_PROMOTE_FULL,
    CONST_ROLLOUT_FIELD_RESTART_AT,
)
from devops_cli.config.defaults import DEFAULT_K8S_NAMESPACE
from devops_cli.core.validation import is_valid_k8s_name
from devops_cli.exceptions.argo import ArgoError, ArgoResourceNotFoundError
from devops_cli.models.argo import ArgoResourceState, ArgoRolloutState, ArgoWorkflowState

logger = logging.getLogger(__name__)

_HTTP_NOT_FOUND = 404


def _is_not_found(exc: Exception) -> bool:
    """Detect a Kubernetes API 404 without importing the client at module scope."""
    return int(getattr(exc, "status", 0) or 0) == _HTTP_NOT_FOUND


def _require_k8s_name(value: str, label: str, *, namespace: bool = False) -> None:
    """Validate an RFC 1123 name, raising a domain error rather than a CLI exit.

    `validate_k8s_name` aborts the process with `typer.Exit`, which is correct at the CLI
    boundary but wrong in a library consumed by FastMCP tools and the TUI as well.
    """
    if not is_valid_k8s_name(value, namespace=namespace):
        raise ArgoError(f"Invalid {label}: {value!r}. Must be a valid RFC 1123 name.")


class ArgoCRDService:
    """In-process Argo custom resource client for Applications, Rollouts, and Workflows.

    Every read and mutation is a direct Kubernetes API call against the `argoproj.io`
    group, replacing shell return-code checks with typed exceptions.
    """

    def __init__(self, context: str | None = None) -> None:
        self.context = context

    def _api(self) -> Any:
        """Resolve the cached in-process CustomObjectsApi client."""
        from devops_cli.k8s.service import KubernetesService

        return KubernetesService.get_instance().custom_objects_api(context=self.context)

    # -- Generic custom resource access ---------------------------------------

    def list_resources(
        self, plural: str, namespace: str = DEFAULT_K8S_NAMESPACE
    ) -> list[dict[str, Any]]:
        """List Argo custom resources of one kind within a namespace."""
        _require_k8s_name(namespace, "namespace", namespace=True)
        try:
            response = self._api().list_namespaced_custom_object(
                group=CONST_ARGO_API_GROUP,
                version=CONST_ARGO_API_VERSION,
                namespace=namespace,
                plural=plural,
            )
        except ArgoError:
            raise
        except Exception as exc:
            raise ArgoError(f"Failed listing Argo '{plural}': {exc}", namespace=namespace) from exc
        return [dict(item) for item in (response or {}).get("items", [])]

    def get_resource(
        self, plural: str, name: str, namespace: str = DEFAULT_K8S_NAMESPACE
    ) -> dict[str, Any]:
        """Fetch a single Argo custom resource, raising a typed error when absent."""
        _require_k8s_name(name, f"{plural} name")
        _require_k8s_name(namespace, "namespace", namespace=True)
        try:
            resource = self._api().get_namespaced_custom_object(
                group=CONST_ARGO_API_GROUP,
                version=CONST_ARGO_API_VERSION,
                namespace=namespace,
                plural=plural,
                name=name,
            )
        except Exception as exc:
            if _is_not_found(exc):
                raise ArgoResourceNotFoundError(
                    f"Argo {plural[:-1]} '{name}' not found in namespace '{namespace}'",
                    resource=name,
                    namespace=namespace,
                ) from exc
            raise ArgoError(
                f"Failed fetching Argo {plural[:-1]} '{name}': {exc}",
                resource=name,
                namespace=namespace,
            ) from exc
        return dict(resource or {})

    def patch_resource(
        self,
        plural: str,
        name: str,
        patch: dict[str, Any],
        namespace: str = DEFAULT_K8S_NAMESPACE,
    ) -> dict[str, Any]:
        """Apply a merge patch to an Argo custom resource."""
        _require_k8s_name(name, f"{plural} name")
        _require_k8s_name(namespace, "namespace", namespace=True)
        try:
            patched = self._api().patch_namespaced_custom_object(
                group=CONST_ARGO_API_GROUP,
                version=CONST_ARGO_API_VERSION,
                namespace=namespace,
                plural=plural,
                name=name,
                body=patch,
            )
        except Exception as exc:
            if _is_not_found(exc):
                raise ArgoResourceNotFoundError(
                    f"Argo {plural[:-1]} '{name}' not found in namespace '{namespace}'",
                    resource=name,
                    namespace=namespace,
                ) from exc
            raise ArgoError(
                f"Failed patching Argo {plural[:-1]} '{name}': {exc}",
                resource=name,
                namespace=namespace,
            ) from exc
        return dict(patched or {})

    def apply_resource(
        self, plural: str, manifest: dict[str, Any], namespace: str = DEFAULT_K8S_NAMESPACE
    ) -> dict[str, Any]:
        """Create an Argo custom resource, patching it in place when it already exists."""
        name = str((manifest.get("metadata") or {}).get("name", ""))
        if not name:
            raise ArgoError(
                f"Argo {plural[:-1]} manifest is missing 'metadata.name'", namespace=namespace
            )
        _require_k8s_name(name, f"{plural} name")
        _require_k8s_name(namespace, "namespace", namespace=True)
        try:
            created = self._api().create_namespaced_custom_object(
                group=CONST_ARGO_API_GROUP,
                version=CONST_ARGO_API_VERSION,
                namespace=namespace,
                plural=plural,
                body=manifest,
            )
        except Exception as exc:
            logger.debug("Argo %s '%s' create rejected (%s); patching in place", plural, name, exc)
            return self.patch_resource(plural, name, manifest, namespace=namespace)
        return dict(created or {})

    # -- Applications & ApplicationSets ---------------------------------------

    def list_applications(self, namespace: str = DEFAULT_K8S_NAMESPACE) -> list[ArgoResourceState]:
        """List ArgoCD Applications as typed resource states."""
        return [
            ArgoResourceState.from_manifest(item)
            for item in self.list_resources(CONST_ARGO_PLURAL_APPLICATIONS, namespace=namespace)
        ]

    def list_application_sets(
        self, namespace: str = DEFAULT_K8S_NAMESPACE
    ) -> list[ArgoResourceState]:
        """List ArgoCD ApplicationSets as typed resource states."""
        return [
            ArgoResourceState.from_manifest(item)
            for item in self.list_resources(CONST_ARGO_PLURAL_APPLICATION_SETS, namespace=namespace)
        ]

    def apply_application(
        self, manifest: dict[str, Any], namespace: str = DEFAULT_K8S_NAMESPACE
    ) -> ArgoResourceState:
        """Apply an ArgoCD Application manifest natively, without `kubectl apply`."""
        return ArgoResourceState.from_manifest(
            self.apply_resource(CONST_ARGO_PLURAL_APPLICATIONS, manifest, namespace=namespace)
        )

    # -- Rollouts -------------------------------------------------------------

    def list_rollouts(self, namespace: str = DEFAULT_K8S_NAMESPACE) -> list[ArgoRolloutState]:
        """List Argo Rollouts as typed progressive delivery states."""
        return [
            ArgoRolloutState.from_manifest(item)
            for item in self.list_resources(CONST_ARGO_PLURAL_ROLLOUTS, namespace=namespace)
        ]

    def get_rollout(self, name: str, namespace: str = DEFAULT_K8S_NAMESPACE) -> ArgoRolloutState:
        """Fetch a single Argo Rollout as a typed progressive delivery state."""
        return ArgoRolloutState.from_manifest(
            self.get_resource(CONST_ARGO_PLURAL_ROLLOUTS, name, namespace=namespace)
        )

    def promote_rollout(
        self, name: str, namespace: str = DEFAULT_K8S_NAMESPACE, *, full: bool = False
    ) -> ArgoRolloutState:
        """Promote a Rollout by clearing its pause conditions via the control-plane fields."""
        status: dict[str, Any] = {
            CONST_ROLLOUT_FIELD_PAUSE_CONDITIONS: None,
            CONST_ROLLOUT_FIELD_CONTROLLER_PAUSE: False,
        }
        if full:
            status[CONST_ROLLOUT_FIELD_PROMOTE_FULL] = True
        return ArgoRolloutState.from_manifest(
            self.patch_resource(
                CONST_ARGO_PLURAL_ROLLOUTS, name, {"status": status}, namespace=namespace
            )
        )

    def abort_rollout(self, name: str, namespace: str = DEFAULT_K8S_NAMESPACE) -> ArgoRolloutState:
        """Abort an in-progress Rollout, reverting traffic to the stable revision."""
        return ArgoRolloutState.from_manifest(
            self.patch_resource(
                CONST_ARGO_PLURAL_ROLLOUTS,
                name,
                {"status": {CONST_ROLLOUT_FIELD_ABORT: True}},
                namespace=namespace,
            )
        )

    def restart_rollout(
        self, name: str, namespace: str = DEFAULT_K8S_NAMESPACE
    ) -> ArgoRolloutState:
        """Restart a Rollout by stamping `spec.restartAt`, which the controller watches."""
        restart_at = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return ArgoRolloutState.from_manifest(
            self.patch_resource(
                CONST_ARGO_PLURAL_ROLLOUTS,
                name,
                {"spec": {CONST_ROLLOUT_FIELD_RESTART_AT: restart_at}},
                namespace=namespace,
            )
        )

    def list_analysis_runs(self, namespace: str = DEFAULT_K8S_NAMESPACE) -> list[ArgoResourceState]:
        """List Rollout AnalysisRuns backing automated canary metric verification."""
        return [
            ArgoResourceState.from_manifest(item)
            for item in self.list_resources(CONST_ARGO_PLURAL_ANALYSIS_RUNS, namespace=namespace)
        ]

    # -- Workflows ------------------------------------------------------------

    def list_workflows(self, namespace: str = DEFAULT_K8S_NAMESPACE) -> list[ArgoWorkflowState]:
        """List Argo Workflows as typed execution states."""
        return [
            ArgoWorkflowState.from_manifest(item)
            for item in self.list_resources(CONST_ARGO_PLURAL_WORKFLOWS, namespace=namespace)
        ]

    def get_workflow(self, name: str, namespace: str = DEFAULT_K8S_NAMESPACE) -> ArgoWorkflowState:
        """Fetch a single Argo Workflow as a typed execution state."""
        return ArgoWorkflowState.from_manifest(
            self.get_resource(CONST_ARGO_PLURAL_WORKFLOWS, name, namespace=namespace)
        )

    def submit_workflow(
        self, manifest: dict[str, Any], namespace: str = DEFAULT_K8S_NAMESPACE
    ) -> ArgoWorkflowState:
        """Submit an Argo Workflow manifest natively, without the `argo` CLI."""
        return ArgoWorkflowState.from_manifest(
            self.apply_resource(CONST_ARGO_PLURAL_WORKFLOWS, manifest, namespace=namespace)
        )

    def workflow_pod_names(self, name: str, namespace: str = DEFAULT_K8S_NAMESPACE) -> list[str]:
        """Resolve the pod names backing a Workflow's nodes for native log streaming."""
        nodes = (self.get_resource(CONST_ARGO_PLURAL_WORKFLOWS, name, namespace=namespace)).get(
            "status", {}
        )
        node_map = (nodes or {}).get("nodes") or {}
        return sorted(
            str(node_id)
            for node_id, node in node_map.items()
            if str((node or {}).get("type", "")) == "Pod"
        )


def get_argo_crd_service(context: str | None = None) -> ArgoCRDService:
    """Construct an Argo custom resource service bound to a kubeconfig context."""
    return ArgoCRDService(context=context)


__all__ = [
    "ArgoCRDService",
    "get_argo_crd_service",
]
