"""Tests for the native Argo custom resource engine and typed state projections.

The engine runs over `cluster`, the Kubernetes API's fake (`tests/support/fakes/kubernetes.py`):
a test seeds the custom objects that the API server holds, calls `ArgoCRDService`, and reads
the objects back or the calls that the fake recorded. A refusal of the API server is a failure
that the fake raises (`fail`, `unreachable`), so the service's own error translation runs.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from devops_cli.argo.crd import ArgoCRDService, get_argo_crd_service, is_not_found_error
from devops_cli.config.constants import (
    CONST_ARGO_API_GROUP,
    CONST_ARGO_API_VERSION,
    CONST_ARGO_PLURAL_ANALYSIS_RUNS,
    CONST_ARGO_PLURAL_APPLICATION_SETS,
    CONST_ARGO_PLURAL_APPLICATIONS,
    CONST_ARGO_PLURAL_ROLLOUTS,
    CONST_ARGO_PLURAL_WORKFLOWS,
)
from devops_cli.exceptions.argo import ArgoError, ArgoResourceNotFoundError
from devops_cli.models.argo import ArgoResourceState, ArgoRolloutState, ArgoWorkflowState
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.kubernetes import FakeCluster, api_exception


def _seed(cluster: FakeCluster, plural: str, *objects: dict[str, Any]) -> None:
    """Put custom objects of `plural` in the cluster, as the API server holds them."""
    key = (CONST_ARGO_API_GROUP, CONST_ARGO_API_VERSION, plural)
    cluster.custom_objects.objects.setdefault(key, []).extend(objects)


def _stored(cluster: FakeCluster, plural: str, name: str) -> dict[str, Any]:
    """The object that the cluster holds under `name`."""
    key = (CONST_ARGO_API_GROUP, CONST_ARGO_API_VERSION, plural)
    return next(
        obj for obj in cluster.custom_objects.objects[key] if obj["metadata"]["name"] == name
    )


def _sent(cluster: FakeCluster, method: str) -> list[dict[str, Any]]:
    """The arguments of each call of `method` that reached the fake API, in order."""
    return [kwargs for name, kwargs in cluster.custom_objects.calls if name == method]


def _rollout(name: str = "web", namespace: str = "apps", **fields: Any) -> dict[str, Any]:
    """A Rollout as the API server holds it."""
    return {"metadata": {"name": name, "namespace": namespace}, **fields}


def _workflow(name: str, namespace: str = "argo", **fields: Any) -> dict[str, Any]:
    """A Workflow as the API server holds it."""
    return {"metadata": {"name": name, "namespace": namespace}, **fields}


@pytest.fixture
def service(cluster: FakeCluster) -> ArgoCRDService:
    """The Argo custom resource service over the fake cluster's current context."""
    return get_argo_crd_service()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Client resolution & error translation
# ─────────────────────────────────────────────────────────────────────────────


def test_service_connects_to_the_context_it_is_bound_to(cluster: FakeCluster) -> None:
    """The service reaches the API of its own kubeconfig context through the shared service."""
    cluster.context_names.append("staging")

    get_argo_crd_service(context="staging").list_resources(
        CONST_ARGO_PLURAL_APPLICATIONS, namespace="argocd"
    )

    assert cluster.connects == ["staging"]


def test_get_argo_crd_service_binds_context() -> None:
    """The factory threads the kubeconfig context onto the constructed service."""
    assert get_argo_crd_service(context="prod").context == "prod"
    assert get_argo_crd_service().context is None


def test_is_not_found_detects_http_404() -> None:
    """A 404 is recognised without importing the Kubernetes client at module scope."""
    assert (
        is_not_found_error(api_exception(404, "Not Found")),
        is_not_found_error(api_exception(500, "Internal Server Error")),
    ) == (True, False)
    assert is_not_found_error(RuntimeError("no status attribute")) is False


def test_missing_resource_raises_typed_not_found(service: ArgoCRDService) -> None:
    """A 404 from the API server becomes an annotated ArgoResourceNotFoundError."""
    with pytest.raises(ArgoResourceNotFoundError) as exc_info:
        service.get_resource(CONST_ARGO_PLURAL_ROLLOUTS, "web", namespace="apps")

    assert (exc_info.value.details["resource"], exc_info.value.details["namespace"]) == (
        "web",
        "apps",
    )


def test_transport_failure_raises_typed_argo_error(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """A non-404 failure becomes an ArgoError rather than a bare shell-style status."""
    cluster.custom_objects.fail(
        "get_namespaced_custom_object", api_exception(503, "Service Unavailable")
    )

    with pytest.raises(ArgoError, match="Failed fetching Argo rollout"):
        service.get_resource(CONST_ARGO_PLURAL_ROLLOUTS, "web", namespace="apps")


def test_listing_failure_raises_typed_argo_error(cluster: FakeCluster) -> None:
    """A failed list call is reported as a typed error naming the namespace."""
    cluster.unreachable()

    with pytest.raises(ArgoError, match="Failed listing Argo") as raised:
        get_argo_crd_service().list_resources(CONST_ARGO_PLURAL_APPLICATIONS, namespace="argocd")

    assert raised.value.details["namespace"] == "argocd"


def test_patch_missing_resource_raises_typed_not_found(service: ArgoCRDService) -> None:
    """Patching an absent resource reports not-found rather than a generic failure."""
    with pytest.raises(ArgoResourceNotFoundError) as raised:
        service.patch_resource(CONST_ARGO_PLURAL_ROLLOUTS, "web", {"status": {}}, namespace="apps")

    assert raised.value.error_code == "ARGO_RESOURCE_NOT_FOUND"


def test_patch_transport_failure_raises_typed_argo_error(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """A rejected patch surfaces as a typed ArgoError."""
    cluster.custom_objects.fail("patch_namespaced_custom_object", api_exception(409, "Conflict"))

    with pytest.raises(ArgoError, match="Failed patching Argo rollout"):
        service.patch_resource(CONST_ARGO_PLURAL_ROLLOUTS, "web", {"status": {}}, namespace="apps")


def test_status_patch_of_a_missing_resource_raises_typed_not_found(
    service: ArgoCRDService,
) -> None:
    """A status patch of an absent resource reports not-found."""
    with pytest.raises(ArgoResourceNotFoundError, match="'web' not found in namespace 'apps'"):
        service.abort_rollout("web", "apps")


def test_status_patch_transport_failure_raises_typed_argo_error(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """A rejected status patch surfaces as a typed ArgoError."""
    cluster.custom_objects.fail(
        "patch_namespaced_custom_object_status", api_exception(500, "Internal Server Error")
    )

    with pytest.raises(ArgoError, match="Failed patching Argo rollout 'web' status"):
        service.abort_rollout("web", "apps")


def test_invalid_names_are_rejected_before_reaching_the_api(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """Name validation runs before any API call and raises a domain error, not a CLI exit.

    This service is consumed by FastMCP tools and the TUI as well as the CLI, so it must
    not abort the process the way `validate_k8s_name` does at the command boundary.
    """
    with pytest.raises(ArgoError, match="Must be a valid RFC 1123 name"):
        service.get_resource(CONST_ARGO_PLURAL_ROLLOUTS, "Invalid Name!", namespace="apps")
    with pytest.raises(ArgoError, match="Must be a valid RFC 1123 name"):
        service.list_resources(CONST_ARGO_PLURAL_ROLLOUTS, namespace="Not A Namespace")

    assert cluster.custom_objects.calls == []


# ─────────────────────────────────────────────────────────────────────────────
# 2. Applications & manifest application
# ─────────────────────────────────────────────────────────────────────────────


def test_list_applications_projects_typed_states(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """Applications are returned as typed states carrying sync and health status."""
    _seed(
        cluster,
        CONST_ARGO_PLURAL_APPLICATIONS,
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
        },
    )

    apps = service.list_applications(namespace="argocd")

    assert [(a.name, a.project, a.sync_status, a.health_status, a.revision) for a in apps] == [
        ("guestbook", "default", "Synced", "Healthy", "abcdef12")
    ]
    call = _sent(cluster, "list_namespaced_custom_object")[0]
    assert (call["group"], call["version"], call["plural"]) == (
        CONST_ARGO_API_GROUP,
        CONST_ARGO_API_VERSION,
        CONST_ARGO_PLURAL_APPLICATIONS,
    )


def test_list_application_sets_and_analysis_runs(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """ApplicationSets and AnalysisRuns project through the same typed state model."""
    for plural in (CONST_ARGO_PLURAL_APPLICATION_SETS, CONST_ARGO_PLURAL_ANALYSIS_RUNS):
        _seed(cluster, plural, {"metadata": {"name": "r1", "namespace": "argocd"}})

    assert [a.name for a in service.list_application_sets(namespace="argocd")] == ["r1"]
    assert [a.name for a in service.list_analysis_runs(namespace="argocd")] == ["r1"]


def test_apply_application_creates_when_absent(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """A new Application manifest is created directly through the API server."""
    manifest = {"metadata": {"name": "root-app"}, "spec": {"project": "default"}}

    applied = service.apply_application(manifest, namespace="argocd")

    assert applied.name == "root-app"
    assert _stored(cluster, CONST_ARGO_PLURAL_APPLICATIONS, "root-app")["spec"] == {
        "project": "default"
    }
    assert _sent(cluster, "patch_namespaced_custom_object") == []


def test_apply_application_patches_when_already_present(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """An Application that already exists is patched in place rather than failing."""
    _seed(
        cluster,
        CONST_ARGO_PLURAL_APPLICATIONS,
        {"metadata": {"name": "root-app", "namespace": "argocd"}, "spec": {"project": "old"}},
    )
    manifest = {"metadata": {"name": "root-app"}, "spec": {"project": "default"}}

    applied = service.apply_application(manifest, namespace="argocd")

    assert applied.name == "root-app"
    assert _stored(cluster, CONST_ARGO_PLURAL_APPLICATIONS, "root-app")["spec"] == {
        "project": "default"
    }
    assert len(_sent(cluster, "patch_namespaced_custom_object")) == 1


def test_apply_resource_requires_manifest_name(service: ArgoCRDService) -> None:
    """A manifest without metadata.name is rejected with an actionable message."""
    with pytest.raises(ArgoError, match=re.escape("missing 'metadata.name'")):
        service.apply_resource(CONST_ARGO_PLURAL_APPLICATIONS, {}, namespace="argocd")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Rollout control-plane mutations
# ─────────────────────────────────────────────────────────────────────────────


def test_promote_rollout_clears_pause_conditions(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """Promotion clears the pause conditions the rollouts controller watches."""
    _seed(
        cluster,
        CONST_ARGO_PLURAL_ROLLOUTS,
        _rollout(spec={}, status={"pauseConditions": [{"reason": "CanaryPauseStep"}]}),
    )

    service.promote_rollout("web", "apps")

    body = _sent(cluster, "patch_namespaced_custom_object_status")[0]["body"]
    assert body["status"] == {"pauseConditions": None, "controllerPause": False}
    assert _stored(cluster, CONST_ARGO_PLURAL_ROLLOUTS, "web")["status"] == {
        "controllerPause": False
    }
    assert _sent(cluster, "patch_namespaced_custom_object") == []


def test_promote_rollout_full_sets_promote_full(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """A full promotion additionally sets the promoteFull control-plane field."""
    _seed(cluster, CONST_ARGO_PLURAL_ROLLOUTS, _rollout(spec={}))

    service.promote_rollout("web", "apps", full=True)

    assert _stored(cluster, CONST_ARGO_PLURAL_ROLLOUTS, "web")["status"]["promoteFull"] is True


def test_promote_rollout_clears_spec_paused_when_set(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """Promotion clears spec.paused on the main resource when it was set."""
    _seed(cluster, CONST_ARGO_PLURAL_ROLLOUTS, _rollout(spec={"paused": True}))

    service.promote_rollout("web", "apps")

    assert _sent(cluster, "patch_namespaced_custom_object")[0]["body"] == {
        "spec": {"paused": False}
    }
    stored = _stored(cluster, CONST_ARGO_PLURAL_ROLLOUTS, "web")
    assert (stored["spec"]["paused"], stored["status"]["controllerPause"]) == (False, False)


def test_abort_rollout_sets_abort_flag(cluster: FakeCluster, service: ArgoCRDService) -> None:
    """Aborting sets status.abort, reverting traffic to the stable revision."""
    _seed(cluster, CONST_ARGO_PLURAL_ROLLOUTS, _rollout())

    service.abort_rollout("web", "apps")

    assert _sent(cluster, "patch_namespaced_custom_object_status")[0]["body"] == {
        "status": {"abort": True}
    }
    assert _sent(cluster, "patch_namespaced_custom_object") == []


def test_restart_rollout_stamps_restart_at(
    cluster: FakeCluster, service: ArgoCRDService, clock: ClockFake
) -> None:
    """Restarting stamps spec.restartAt with an RFC 3339 UTC timestamp of the clock's time."""
    clock.move_to("2026-09-21T12:00:00Z")
    _seed(cluster, CONST_ARGO_PLURAL_ROLLOUTS, _rollout())

    service.restart_rollout("web", "apps")

    assert _stored(cluster, CONST_ARGO_PLURAL_ROLLOUTS, "web")["spec"] == {
        "restartAt": "2026-09-21T12:00:00Z"
    }


def test_get_rollout_projects_canary_progress(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """A Rollout projects into a typed progressive delivery state."""
    _seed(
        cluster,
        CONST_ARGO_PLURAL_ROLLOUTS,
        _rollout(
            spec={
                "replicas": 4,
                "strategy": {"canary": {"steps": [{"setWeight": 25}, {"pause": {}}]}},
            },
            status={
                "phase": "Paused",
                "message": "waiting at step 1",
                "currentStepIndex": 1,
                "readyReplicas": 3,
                "updatedReplicas": 1,
                "availableReplicas": 3,
                "pauseConditions": [{"reason": "CanaryPauseStep"}],
            },
        ),
    )

    state = service.get_rollout("web", "apps")

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


def test_list_rollouts_projects_each_item(cluster: FakeCluster, service: ArgoCRDService) -> None:
    """Every Rollout in the namespace is projected into a typed state."""
    _seed(
        cluster,
        CONST_ARGO_PLURAL_ROLLOUTS,
        _rollout("a", status={"phase": "Healthy"}),
        _rollout("b", status={"phase": "Degraded"}),
        _rollout("elsewhere", "other", status={"phase": "Healthy"}),
    )

    states = service.list_rollouts(namespace="apps")

    assert [(s.name, s.phase) for s in states] == [("a", "Healthy"), ("b", "Degraded")]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Workflows
# ─────────────────────────────────────────────────────────────────────────────


def test_submit_workflow_creates_resource(cluster: FakeCluster, service: ArgoCRDService) -> None:
    """Workflow submission posts the manifest directly, without the argo CLI."""
    state = service.submit_workflow(
        {"metadata": {"name": "build"}, "status": {"phase": "Running"}}, namespace="argo"
    )

    assert (state.name, state.phase) == ("build", "Running")
    assert _sent(cluster, "create_namespaced_custom_object")[0]["plural"] == (
        CONST_ARGO_PLURAL_WORKFLOWS
    )


def test_get_workflow_projects_execution_state(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """A Workflow projects phase, timing, progress, and node count."""
    _seed(
        cluster,
        CONST_ARGO_PLURAL_WORKFLOWS,
        _workflow(
            "build",
            status={
                "phase": "Succeeded",
                "message": "all steps completed",
                "startedAt": "2026-09-21T10:00:00Z",
                "finishedAt": "2026-09-21T10:05:00Z",
                "progress": "3/3",
                "nodes": {"n1": {"type": "Pod"}, "n2": {"type": "DAG"}},
            },
        ),
    )

    state = service.get_workflow("build", "argo")

    assert (state.phase, state.progress, state.node_count, state.finished_at) == (
        "Succeeded",
        "3/3",
        2,
        "2026-09-21T10:05:00Z",
    )


def test_workflow_pod_names_selects_only_pod_nodes(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """Only Pod-type DAG nodes back log streaming, returned in stable order."""
    _seed(
        cluster,
        CONST_ARGO_PLURAL_WORKFLOWS,
        {
            "metadata": {
                "name": "build",
                "namespace": "argo",
                "annotations": {"workflows.argoproj.io/pod-name-format": "v1"},
            },
            "status": {
                "nodes": {
                    "build-2": {"type": "Pod"},
                    "build-1": {"type": "Pod"},
                    "build-dag": {"type": "DAG"},
                }
            },
        },
    )

    assert service.workflow_pod_names("build", "argo") == ["build-1", "build-2"]


def test_workflow_pod_names_v2_derived_with_hash(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """Under v2 naming, pod names follow <workflow>-<templateName>-<hash>."""
    _seed(
        cluster,
        CONST_ARGO_PLURAL_WORKFLOWS,
        {
            "metadata": {
                "name": "build",
                "namespace": "argo",
                "annotations": {"workflows.argoproj.io/pod-name-format": "v2"},
            },
            "status": {
                "nodes": {
                    "build-1": {
                        "id": "build-1",
                        "name": "build[0].step-compile",
                        "templateName": "compile",
                        "type": "Pod",
                        "phase": "Succeeded",
                    },
                    "build-2": {
                        "id": "build-2",
                        "name": "build[0].step-test",
                        "templateName": "test",
                        "type": "Pod",
                        "phase": "Running",
                    },
                }
            },
        },
    )

    assert service.workflow_pod_names("build", "argo") == [
        "build-compile-172156865",
        "build-test-3950655536",
    ]


def test_workflow_pod_names_v2_single_container_matches_workflow(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """When a single container node name matches workflow name, pod name equals workflow name."""
    _seed(
        cluster,
        CONST_ARGO_PLURAL_WORKFLOWS,
        _workflow(
            "hello-wf",
            status={
                "nodes": {
                    "hello-wf": {
                        "id": "hello-wf",
                        "name": "hello-wf",
                        "type": "Pod",
                        "phase": "Succeeded",
                    }
                }
            },
        ),
    )

    assert service.workflow_pod_names("hello-wf", "argo") == ["hello-wf"]


def test_workflow_pod_names_excludes_skipped_and_omitted_nodes(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """Nodes with phase Skipped or Omitted are excluded from pod names."""
    _seed(
        cluster,
        CONST_ARGO_PLURAL_WORKFLOWS,
        {
            "metadata": {
                "name": "wf",
                "namespace": "argo",
                "annotations": {"workflows.argoproj.io/pod-name-format": "v1"},
            },
            "status": {
                "nodes": {
                    "wf-ran": {"id": "wf-ran", "type": "Pod", "phase": "Succeeded"},
                    "wf-skipped": {"id": "wf-skipped", "type": "Pod", "phase": "Skipped"},
                    "wf-omitted": {"id": "wf-omitted", "type": "Pod", "phase": "Omitted"},
                    "wf-dag": {"id": "wf-dag", "type": "DAG", "phase": "Running"},
                }
            },
        },
    )

    assert service.workflow_pod_names("wf", "argo") == ["wf-ran"]


def test_workflow_pod_names_handles_absent_nodes(
    cluster: FakeCluster, service: ArgoCRDService
) -> None:
    """A Workflow that has not scheduled any node yields no pods rather than raising."""
    _seed(cluster, CONST_ARGO_PLURAL_WORKFLOWS, _workflow("build"))

    assert service.workflow_pod_names("build", "argo") == []


def test_list_workflows_projects_each_item(cluster: FakeCluster, service: ArgoCRDService) -> None:
    """Workflow listings project into typed execution states."""
    _seed(cluster, CONST_ARGO_PLURAL_WORKFLOWS, _workflow("w1", status={"phase": "Running"}))

    assert [(w.name, w.phase) for w in service.list_workflows("argo")] == [("w1", "Running")]


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
