"""Unit tests for the native Argo custom resource engine and typed state projections."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.argo.crd import ArgoCRDService, _is_not_found, get_argo_crd_service
from devops_cli.config.constants import (
    CONST_ARGO_API_GROUP,
    CONST_ARGO_API_VERSION,
    CONST_ARGO_PLURAL_APPLICATIONS,
    CONST_ARGO_PLURAL_ROLLOUTS,
    CONST_ARGO_PLURAL_WORKFLOWS,
)
from devops_cli.exceptions.argo import ArgoError, ArgoResourceNotFoundError
from devops_cli.models.argo import ArgoResourceState, ArgoRolloutState, ArgoWorkflowState


class _ApiError(Exception):
    """Stand-in for kubernetes.client.rest.ApiException carrying an HTTP status."""

    def __init__(self, status: int) -> None:
        super().__init__(f"api error {status}")
        self.status = status


@pytest.fixture
def crd_api() -> Any:
    """Provide a mock CustomObjectsApi bound to an ArgoCRDService."""
    return MagicMock()


def _service(api: Any) -> ArgoCRDService:
    """Build a service whose API accessor returns the supplied mock."""
    service = ArgoCRDService()
    service._api = lambda: api  # type: ignore[method-assign]
    return service


# ─────────────────────────────────────────────────────────────────────────────
# 1. Client resolution & error translation
# ─────────────────────────────────────────────────────────────────────────────


def test_api_delegates_to_kubernetes_service() -> None:
    """The CRD service resolves its client from the shared KubernetesService."""
    mock_service = MagicMock()
    with patch("devops_cli.k8s.service.KubernetesService.get_instance", return_value=mock_service):
        ArgoCRDService(context="staging")._api()

    mock_service.custom_objects_api.assert_called_once_with(context="staging")


def test_get_argo_crd_service_binds_context() -> None:
    """The factory threads the kubeconfig context onto the constructed service."""
    assert get_argo_crd_service(context="prod").context == "prod"
    assert get_argo_crd_service().context is None


def test_is_not_found_detects_http_404() -> None:
    """A 404 is recognised without importing the Kubernetes client at module scope."""
    assert (_is_not_found(_ApiError(404)), _is_not_found(_ApiError(500))) == (True, False)
    assert _is_not_found(RuntimeError("no status attribute")) is False


def test_missing_resource_raises_typed_not_found(crd_api: Any) -> None:
    """A 404 from the API server becomes an annotated ArgoResourceNotFoundError."""
    crd_api.get_namespaced_custom_object.side_effect = _ApiError(404)

    with pytest.raises(ArgoResourceNotFoundError) as exc_info:
        _service(crd_api).get_resource(CONST_ARGO_PLURAL_ROLLOUTS, "web", namespace="apps")

    assert (exc_info.value.details["resource"], exc_info.value.details["namespace"]) == (
        "web",
        "apps",
    )


def test_transport_failure_raises_typed_argo_error(crd_api: Any) -> None:
    """A non-404 failure becomes an ArgoError rather than a bare shell-style status."""
    crd_api.get_namespaced_custom_object.side_effect = _ApiError(503)

    with pytest.raises(ArgoError, match="Failed fetching Argo rollout"):
        _service(crd_api).get_resource(CONST_ARGO_PLURAL_ROLLOUTS, "web", namespace="apps")


def test_listing_failure_raises_typed_argo_error(crd_api: Any) -> None:
    """A failed list call is reported as a typed error naming the namespace."""
    crd_api.list_namespaced_custom_object.side_effect = RuntimeError("apiserver down")

    with pytest.raises(ArgoError, match="Failed listing Argo"):
        _service(crd_api).list_resources(CONST_ARGO_PLURAL_APPLICATIONS, namespace="argocd")


def test_patch_missing_resource_raises_typed_not_found(crd_api: Any) -> None:
    """Patching an absent resource reports not-found rather than a generic failure."""
    crd_api.patch_namespaced_custom_object.side_effect = _ApiError(404)

    with pytest.raises(ArgoResourceNotFoundError):
        _service(crd_api).patch_resource(
            CONST_ARGO_PLURAL_ROLLOUTS, "web", {"status": {}}, namespace="apps"
        )


def test_patch_transport_failure_raises_typed_argo_error(crd_api: Any) -> None:
    """A rejected patch surfaces as a typed ArgoError."""
    crd_api.patch_namespaced_custom_object.side_effect = _ApiError(409)

    with pytest.raises(ArgoError, match="Failed patching Argo rollout"):
        _service(crd_api).patch_resource(
            CONST_ARGO_PLURAL_ROLLOUTS, "web", {"status": {}}, namespace="apps"
        )


def test_invalid_names_are_rejected_before_reaching_the_api(crd_api: Any) -> None:
    """Name validation runs before any API call and raises a domain error, not a CLI exit.

    This service is consumed by FastMCP tools and the TUI as well as the CLI, so it must
    not abort the process the way `validate_k8s_name` does at the command boundary.
    """
    service = _service(crd_api)

    with pytest.raises(ArgoError, match="Must be a valid RFC 1123 name"):
        service.get_resource(CONST_ARGO_PLURAL_ROLLOUTS, "Invalid Name!", namespace="apps")
    with pytest.raises(ArgoError, match="Must be a valid RFC 1123 name"):
        service.list_resources(CONST_ARGO_PLURAL_ROLLOUTS, namespace="Not A Namespace")

    assert crd_api.get_namespaced_custom_object.called is False
    assert crd_api.list_namespaced_custom_object.called is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. Applications & manifest application
# ─────────────────────────────────────────────────────────────────────────────


def test_list_applications_projects_typed_states(crd_api: Any) -> None:
    """Applications are returned as typed states carrying sync and health status."""
    crd_api.list_namespaced_custom_object.return_value = {
        "items": [
            {
                "kind": "Application",
                "metadata": {"name": "guestbook", "namespace": "argocd"},
                "spec": {
                    "project": "default",
                    "source": {"repoURL": "https://example.com/org/repo.git"},
                },
                "status": {
                    "sync": {"status": "Synced", "revision": "abcdef1234567890"},
                    "health": {"status": "Healthy"},
                },
            }
        ]
    }
    apps = _service(crd_api).list_applications(namespace="argocd")

    assert len(apps) == 1
    assert (
        apps[0].name,
        apps[0].project,
        apps[0].sync_status,
        apps[0].health_status,
        apps[0].revision,
    ) == ("guestbook", "default", "Synced", "Healthy", "abcdef12")

    call = crd_api.list_namespaced_custom_object.call_args.kwargs
    assert (call["group"], call["version"], call["plural"]) == (
        CONST_ARGO_API_GROUP,
        CONST_ARGO_API_VERSION,
        CONST_ARGO_PLURAL_APPLICATIONS,
    )


def test_list_application_sets_and_analysis_runs(crd_api: Any) -> None:
    """ApplicationSets and AnalysisRuns project through the same typed state model."""
    crd_api.list_namespaced_custom_object.return_value = {"items": [{"metadata": {"name": "r1"}}]}
    service = _service(crd_api)

    assert [a.name for a in service.list_application_sets(namespace="argocd")] == ["r1"]
    assert [a.name for a in service.list_analysis_runs(namespace="argocd")] == ["r1"]


def test_apply_application_creates_when_absent(crd_api: Any) -> None:
    """A new Application manifest is created directly through the API server."""
    manifest = {"metadata": {"name": "root-app"}, "spec": {"project": "default"}}
    crd_api.create_namespaced_custom_object.return_value = {
        "metadata": {"name": "root-app", "namespace": "argocd"}
    }

    applied = _service(crd_api).apply_application(manifest, namespace="argocd")

    assert applied.name == "root-app"
    assert crd_api.patch_namespaced_custom_object.called is False


def test_apply_application_patches_when_already_present(crd_api: Any) -> None:
    """An Application that already exists is patched in place rather than failing."""
    manifest = {"metadata": {"name": "root-app"}, "spec": {"project": "default"}}
    crd_api.create_namespaced_custom_object.side_effect = _ApiError(409)
    crd_api.patch_namespaced_custom_object.return_value = {"metadata": {"name": "root-app"}}

    applied = _service(crd_api).apply_application(manifest, namespace="argocd")

    assert applied.name == "root-app"
    crd_api.patch_namespaced_custom_object.assert_called_once()


def test_apply_resource_requires_manifest_name(crd_api: Any) -> None:
    """A manifest without metadata.name is rejected with an actionable message."""
    with pytest.raises(ArgoError, match="missing 'metadata.name'"):
        _service(crd_api).apply_resource(CONST_ARGO_PLURAL_APPLICATIONS, {}, namespace="argocd")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Rollout control-plane mutations
# ─────────────────────────────────────────────────────────────────────────────


def test_promote_rollout_clears_pause_conditions(crd_api: Any) -> None:
    """Promotion clears the pause conditions the rollouts controller watches."""
    crd_api.patch_namespaced_custom_object.return_value = {"metadata": {"name": "web"}}
    _service(crd_api).promote_rollout("web", "apps")

    body = crd_api.patch_namespaced_custom_object.call_args.kwargs["body"]
    assert body["status"] == {"pauseConditions": None, "controllerPause": False}


def test_promote_rollout_full_sets_promote_full(crd_api: Any) -> None:
    """A full promotion additionally sets the promoteFull control-plane field."""
    crd_api.patch_namespaced_custom_object.return_value = {"metadata": {"name": "web"}}
    _service(crd_api).promote_rollout("web", "apps", full=True)

    assert (
        crd_api.patch_namespaced_custom_object.call_args.kwargs["body"]["status"]["promoteFull"]
        is True
    )


def test_abort_rollout_sets_abort_flag(crd_api: Any) -> None:
    """Aborting sets status.abort, reverting traffic to the stable revision."""
    crd_api.patch_namespaced_custom_object.return_value = {"metadata": {"name": "web"}}
    _service(crd_api).abort_rollout("web", "apps")

    assert crd_api.patch_namespaced_custom_object.call_args.kwargs["body"] == {
        "status": {"abort": True}
    }


def test_restart_rollout_stamps_restart_at(crd_api: Any) -> None:
    """Restarting stamps spec.restartAt with an RFC 3339 UTC timestamp."""
    crd_api.patch_namespaced_custom_object.return_value = {"metadata": {"name": "web"}}
    _service(crd_api).restart_rollout("web", "apps")

    restart_at = crd_api.patch_namespaced_custom_object.call_args.kwargs["body"]["spec"][
        "restartAt"
    ]
    assert restart_at.endswith("Z")
    assert len(restart_at) == len("2026-09-21T12:00:00Z")


def test_get_rollout_projects_canary_progress(crd_api: Any) -> None:
    """A Rollout projects into a typed progressive delivery state."""
    crd_api.get_namespaced_custom_object.return_value = {
        "metadata": {"name": "web", "namespace": "apps"},
        "spec": {
            "replicas": 4,
            "strategy": {"canary": {"steps": [{"setWeight": 25}, {"pause": {}}]}},
        },
        "status": {
            "phase": "Paused",
            "message": "waiting at step 1",
            "currentStepIndex": 1,
            "readyReplicas": 3,
            "updatedReplicas": 1,
            "availableReplicas": 3,
            "pauseConditions": [{"reason": "CanaryPauseStep"}],
        },
    }
    state = _service(crd_api).get_rollout("web", "apps")

    assert (
        state.name,
        state.strategy,
        state.phase,
        state.current_step,
        state.total_steps,
        state.desired_replicas,
        state.ready_replicas,
        state.paused,
        state.aborted,
    ) == ("web", "canary", "Paused", 1, 2, 4, 3, True, False)


def test_list_rollouts_projects_each_item(crd_api: Any) -> None:
    """Every Rollout in the namespace is projected into a typed state."""
    crd_api.list_namespaced_custom_object.return_value = {
        "items": [
            {"metadata": {"name": "a"}, "status": {"phase": "Healthy"}},
            {"metadata": {"name": "b"}, "status": {"phase": "Degraded"}},
        ]
    }
    states = _service(crd_api).list_rollouts(namespace="apps")
    assert [(s.name, s.phase) for s in states] == [("a", "Healthy"), ("b", "Degraded")]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Workflows
# ─────────────────────────────────────────────────────────────────────────────


def test_submit_workflow_creates_resource(crd_api: Any) -> None:
    """Workflow submission posts the manifest directly, without the argo CLI."""
    crd_api.create_namespaced_custom_object.return_value = {
        "metadata": {"name": "build"},
        "status": {"phase": "Running"},
    }
    state = _service(crd_api).submit_workflow({"metadata": {"name": "build"}}, namespace="argo")

    assert (state.name, state.phase) == ("build", "Running")
    assert crd_api.create_namespaced_custom_object.call_args.kwargs["plural"] == (
        CONST_ARGO_PLURAL_WORKFLOWS
    )


def test_get_workflow_projects_execution_state(crd_api: Any) -> None:
    """A Workflow projects phase, timing, progress, and node count."""
    crd_api.get_namespaced_custom_object.return_value = {
        "metadata": {"name": "build", "namespace": "argo"},
        "status": {
            "phase": "Succeeded",
            "message": "all steps completed",
            "startedAt": "2026-09-21T10:00:00Z",
            "finishedAt": "2026-09-21T10:05:00Z",
            "progress": "3/3",
            "nodes": {"n1": {"type": "Pod"}, "n2": {"type": "DAG"}},
        },
    }
    state = _service(crd_api).get_workflow("build", "argo")

    assert (state.phase, state.progress, state.node_count, state.finished_at) == (
        "Succeeded",
        "3/3",
        2,
        "2026-09-21T10:05:00Z",
    )


def test_workflow_pod_names_selects_only_pod_nodes(crd_api: Any) -> None:
    """Only Pod-type DAG nodes back log streaming, returned in stable order."""
    crd_api.get_namespaced_custom_object.return_value = {
        "metadata": {"name": "build"},
        "status": {
            "nodes": {
                "build-2": {"type": "Pod"},
                "build-1": {"type": "Pod"},
                "build-dag": {"type": "DAG"},
            }
        },
    }
    assert _service(crd_api).workflow_pod_names("build", "argo") == ["build-1", "build-2"]


def test_workflow_pod_names_handles_absent_nodes(crd_api: Any) -> None:
    """A Workflow that has not scheduled any node yields no pods rather than raising."""
    crd_api.get_namespaced_custom_object.return_value = {"metadata": {"name": "build"}}
    assert _service(crd_api).workflow_pod_names("build", "argo") == []


def test_list_workflows_projects_each_item(crd_api: Any) -> None:
    """Workflow listings project into typed execution states."""
    crd_api.list_namespaced_custom_object.return_value = {
        "items": [{"metadata": {"name": "w1"}, "status": {"phase": "Running"}}]
    }
    assert [(w.name, w.phase) for w in _service(crd_api).list_workflows("argo")] == [
        ("w1", "Running")
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Typed state projections
# ─────────────────────────────────────────────────────────────────────────────


def test_states_tolerate_sparse_and_malformed_payloads() -> None:
    """Projections never raise on absent, null, or wrongly typed resource sections."""
    sparse = ArgoResourceState.from_manifest({})
    malformed = ArgoResourceState.from_manifest(
        {"metadata": None, "spec": "not-a-dict", "status": 42}
    )
    rollout = ArgoRolloutState.from_manifest({})
    workflow = ArgoWorkflowState.from_manifest({"status": None})

    assert (sparse.name, sparse.sync_status, sparse.health_status) == ("", "Unknown", "Unknown")
    assert (malformed.name, malformed.project, malformed.repo_url) == ("", "", "")
    assert (rollout.phase, rollout.total_steps, rollout.paused, rollout.current_step) == (
        "Unknown",
        0,
        False,
        None,
    )
    assert (workflow.phase, workflow.node_count, workflow.started_at) == ("Unknown", 0, "")


def test_blue_green_strategy_is_detected() -> None:
    """A Rollout without a canary block reports the blueGreen strategy."""
    state = ArgoRolloutState.from_manifest(
        {"spec": {"strategy": {"blueGreen": {"activeService": "web"}}}}
    )
    assert (state.strategy, state.total_steps) == ("blueGreen", 0)


def test_aborted_rollout_is_reported() -> None:
    """An aborted Rollout surfaces the abort flag in its typed state."""
    assert ArgoRolloutState.from_manifest({"status": {"abort": True}}).aborted is True
