"""`await_workflow` polls a Workflow to a terminal phase on the Kubernetes API fake (#1335).

The cluster is `FakeCluster` and time is `ClockFake`, so no test waits in real time. A test
changes the Workflow in the cluster while `await_workflow` waits, through the clock's
`after_each_sleep` hook, as the Argo controller changes it in a real cluster.
"""

from __future__ import annotations

import pytest

from devops_cli.argo.crd import get_argo_crd_service
from devops_cli.argo.workflows import await_workflow
from devops_cli.config.constants import (
    CONST_ARGO_API_GROUP,
    CONST_ARGO_API_VERSION,
    CONST_ARGO_PLURAL_WORKFLOWS,
)
from devops_cli.exceptions.argo import (
    ArgoError,
    ArgoResourceNotFoundError,
    ArgoWorkflowTimeoutError,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.kubernetes import FakeCluster

_WORKFLOWS = (CONST_ARGO_API_GROUP, CONST_ARGO_API_VERSION, CONST_ARGO_PLURAL_WORKFLOWS)


def _seed_workflow(cluster: FakeCluster, phase: str) -> dict[str, dict[str, str]]:
    """Put the Workflow `build` in the namespace `argo` of the cluster, in `phase`."""
    workflow = {
        "metadata": {"name": "build", "namespace": "argo"},
        "status": {"phase": phase},
    }
    cluster.custom_objects.objects[_WORKFLOWS] = [workflow]
    return workflow


def test_a_finished_workflow_returns_at_once(cluster: FakeCluster, clock: ClockFake) -> None:
    """A Workflow in a terminal phase is read one time, and the wait does not sleep."""
    _seed_workflow(cluster, "Succeeded")

    state = await_workflow(get_argo_crd_service(), "build", "argo")

    assert (state.phase, clock.waits, len(cluster.custom_objects.calls)) == ("Succeeded", [], 1)


def test_a_running_workflow_is_polled_until_its_phase_turns_terminal(
    cluster: FakeCluster, clock: ClockFake
) -> None:
    """The wait sleeps one poll interval between reads, and returns the first terminal state."""
    seeded = _seed_workflow(cluster, "Running")

    def controller_finishes_after_two_waits() -> None:
        if len(clock.waits) == 2:
            seeded["status"]["phase"] = "Failed"

    clock.after_each_sleep(controller_finishes_after_two_waits)

    state = await_workflow(get_argo_crd_service(), "build", "argo", timeout=60, poll_interval=5)

    assert (state.phase, clock.waits, len(cluster.custom_objects.calls)) == (
        "Failed",
        [5.0, 5.0],
        3,
    )


def test_a_workflow_that_stays_running_raises_the_timeout_error(
    cluster: FakeCluster, clock: ClockFake
) -> None:
    """When the budget ends before a terminal phase, the error names the Workflow and its wait."""
    _seed_workflow(cluster, "Running")

    with pytest.raises(ArgoWorkflowTimeoutError) as raised:
        await_workflow(get_argo_crd_service(), "build", "argo", timeout=20, poll_interval=5)

    assert (
        raised.value.error_code,
        str(raised.value),
        raised.value.details["resource"],
        raised.value.details["namespace"],
        sum(clock.waits),
    ) == (
        "ARGO_WORKFLOW_TIMEOUT",
        "Timed out after 20s waiting for workflow 'build' to reach a terminal phase.",
        "build",
        "argo",
        20.0,
    )


def test_a_missing_workflow_raises_the_not_found_error_at_once(
    cluster: FakeCluster, clock: ClockFake
) -> None:
    """The first read fails for a Workflow that the cluster does not hold; the wait is not retried."""
    with pytest.raises(ArgoResourceNotFoundError, match="'build' not found in namespace 'argo'"):
        await_workflow(get_argo_crd_service(), "build", "argo")

    assert clock.waits == []


def test_a_read_that_fails_while_waiting_ends_the_wait(
    cluster: FakeCluster, clock: ClockFake
) -> None:
    """An API failure on a later read leaves the wait with the typed error."""
    _seed_workflow(cluster, "Running")

    def api_server_goes_down() -> None:
        cluster.unreachable()

    clock.after_each_sleep(api_server_goes_down)

    with pytest.raises(ArgoError, match="Failed fetching Argo workflow"):
        await_workflow(get_argo_crd_service(), "build", "argo", timeout=60, poll_interval=5)

    assert clock.waits == [5.0]
