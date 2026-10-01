"""Tests for the Kubernetes models: the pod status kubectl prints, node readiness and events.

Every surface that lists pods reads its STATUS and READY from `PodInfo.from_pod`, so the
cases kubectl distinguishes are pinned here once, table-driven, against the SDK's own
objects.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from kubernetes import client  # type: ignore[import-untyped]
from typer.testing import CliRunner

import devops_cli.ui.data_providers as data_providers
from devops_cli.commands.k8s import app as k8s_app
from devops_cli.commands.k8s.diagnostics import _build_pods_table
from devops_cli.k8s.service import KubernetesService
from devops_cli.models.k8s import ContainerInfo, PodEventInfo, PodInfo, node_is_ready
from devops_cli.output import Text
from devops_cli.ui.projections import k8s_rows
from tests.k8s_fakes import (
    NOW,
    FakeCoreV1,
    crashlooping_pod,
    event,
    healthy_pod,
    node,
    pod,
    ready_app,
    running,
    status,
    terminated,
    waiting,
)

runner = CliRunner()

# =============================================================================
# Pod Status
# =============================================================================

STATUS_CASES: dict[str, tuple[Any, str, str]] = {
    "crashloop-in-a-running-pod": (
        pod(statuses=[status("app", waiting("CrashLoopBackOff"), restarts=86)]),
        "CrashLoopBackOff",
        "0/1",
    ),
    "container-creating": (
        pod(phase="Pending", statuses=[status("app", waiting("ContainerCreating"))]),
        "ContainerCreating",
        "0/1",
    ),
    "completed": (
        pod(phase="Succeeded", statuses=[status("app", terminated(0, "Completed"))]),
        "Completed",
        "0/1",
    ),
    "oom-killed": (
        pod(phase="Failed", statuses=[status("app", terminated(137, "OOMKilled"))]),
        "OOMKilled",
        "0/1",
    ),
    "exit-code-without-reason": (
        pod(phase="Failed", statuses=[status("app", terminated(1))]),
        "ExitCode:1",
        "0/1",
    ),
    "signal-without-reason": (
        pod(phase="Failed", statuses=[status("app", terminated(137, signal=9))]),
        "Signal:9",
        "0/1",
    ),
    "completed-beside-running-not-ready": (
        pod(
            containers=("app", "job"),
            statuses=[ready_app(), status("job", terminated(0, "Completed"))],
            conditions={"Ready": "False"},
        ),
        "NotReady",
        "1/2",
    ),
    "completed-beside-running-ready": (
        pod(
            containers=("app", "job"),
            statuses=[ready_app(), status("job", terminated(0, "Completed"))],
            conditions={"Ready": "True"},
        ),
        "Running",
        "1/2",
    ),
    "init-in-progress": (
        pod(
            phase="Pending",
            init_containers=("migrate", "seed"),
            init_statuses=[
                status("migrate", running()),
                status("seed", waiting("PodInitializing")),
            ],
            statuses=[status("app", waiting("PodInitializing"))],
        ),
        "Init:0/2",
        "0/1",
    ),
    "init-crashloop": (
        pod(
            phase="Pending",
            init_containers=("migrate",),
            init_statuses=[status("migrate", waiting("CrashLoopBackOff"), restarts=4)],
            statuses=[status("app", waiting("PodInitializing"))],
        ),
        "Init:CrashLoopBackOff",
        "0/1",
    ),
    "init-exit-code": (
        pod(
            phase="Pending",
            init_containers=("migrate",),
            init_statuses=[status("migrate", terminated(1))],
            statuses=[status("app", waiting("PodInitializing"))],
        ),
        "Init:ExitCode:1",
        "0/1",
    ),
    "init-signal": (
        pod(
            phase="Pending",
            init_containers=("migrate",),
            init_statuses=[status("migrate", terminated(137, signal=9))],
        ),
        "Init:Signal:9",
        "0/1",
    ),
    "init-terminated-reason": (
        pod(
            phase="Pending",
            init_containers=("migrate",),
            init_statuses=[status("migrate", terminated(1, "Error"))],
        ),
        "Init:Error",
        "0/1",
    ),
    "running-sidecar-and-ready-app": (
        pod(
            init_containers=("proxy",),
            sidecars=("proxy",),
            init_statuses=[status("proxy", running(), ready=True, started=True)],
            statuses=[ready_app()],
            conditions={"Initialized": "True", "Ready": "True"},
        ),
        "Running",
        "2/2",
    ),
    "finished-init-then-running": (
        pod(
            init_containers=("migrate",),
            init_statuses=[status("migrate", terminated(0, "Completed"))],
            statuses=[ready_app()],
        ),
        "Running",
        "1/1",
    ),
    "evicted": (pod(phase="Failed", reason="Evicted"), "Evicted", "0/1"),
    "unscheduled": (
        pod(phase="Pending", conditions={"PodScheduled": "False"}),
        "Pending",
        "0/1",
    ),
    "terminating": (pod(statuses=[ready_app()], deleted=True), "Terminating", "1/1"),
    "node-lost": (
        pod(statuses=[ready_app()], reason="NodeLost", deleted=True),
        "Unknown",
        "1/1",
    ),
    "deleted-after-completing": (
        pod(phase="Succeeded", statuses=[status("app", terminated(0, "Completed"))], deleted=True),
        "Completed",
        "0/1",
    ),
    "running": (
        pod(containers=("app", "web"), statuses=[ready_app(), ready_app("web")]),
        "Running",
        "2/2",
    ),
}


@pytest.mark.parametrize(
    ("api_pod", "expected_status", "expected_ready"), STATUS_CASES.values(), ids=STATUS_CASES
)
def test_from_pod_reports_the_status_and_ready_kubectl_prints(
    api_pod: Any, expected_status: str, expected_ready: str
) -> None:
    """STATUS is the reason a container gives, not the phase, which hid every crashloop."""
    info = PodInfo.from_pod(api_pod)
    assert (info.status, info.ready_containers) == (expected_status, expected_ready)


def test_a_scheduling_gated_pod_reads_scheduling_gated() -> None:
    """A pod held back by a scheduling gate says so, as kubectl does."""
    gated = pod(phase="Pending")
    gated.status.conditions = [
        client.V1PodCondition(type="PodScheduled", status="False", reason="SchedulingGated")
    ]
    assert PodInfo.from_pod(gated).status == "SchedulingGated"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("running", False),
        ("completed", False),
        ("crashloop-in-a-running-pod", True),
        ("container-creating", True),
        ("completed-beside-running-ready", True),
        ("init-in-progress", True),
        ("evicted", True),
    ],
)
def test_a_pod_is_unhealthy_unless_it_runs_ready_or_completed(name: str, expected: bool) -> None:
    """A Running pod short of READY needs attention; a Completed one is simply done."""
    assert PodInfo.from_pod(STATUS_CASES[name][0]).unhealthy is expected


def test_restarts_count_the_app_containers_once_initialised() -> None:
    """RESTARTS adds the app containers and the sidecars, as kubectl does."""
    api_pod = pod(
        containers=("app", "web"),
        init_containers=("migrate", "proxy"),
        sidecars=("proxy",),
        init_statuses=[
            status("migrate", terminated(0, "Completed"), restarts=5),
            status("proxy", running(), ready=True, started=True, restarts=2),
        ],
        statuses=[status("app", running(), ready=True, restarts=3), ready_app("web")],
    )
    assert PodInfo.from_pod(api_pod).restart_count == 5


def test_restarts_count_the_init_containers_while_initialising() -> None:
    """Until initialisation finishes, the init containers' restarts are what is happening."""
    info = PodInfo.from_pod(STATUS_CASES["init-crashloop"][0])
    assert (info.status, info.restart_count) == ("Init:CrashLoopBackOff", 4)


def test_from_pod_records_each_container_with_its_state_and_last_termination() -> None:
    """The inspector lists every container from the record, so it needs no API call."""
    info = PodInfo.from_pod(crashlooping_pod("web-0", "shop"))
    assert (info.name, info.namespace, info.uid, info.containers) == (
        "web-0",
        "shop",
        "uid-shop-web-0",
        [
            ContainerInfo(
                name="app",
                image="example.com/app:1",
                ready=False,
                restarts=86,
                state="Waiting",
                reason="CrashLoopBackOff",
                last_termination_reason="Error",
                last_exit_code=1,
            )
        ],
    )


def test_init_containers_are_recorded_apart_and_sidecars_marked_restartable() -> None:
    """`c` cycles through init containers too, and a sidecar is a long-lived one."""
    info = PodInfo.from_pod(STATUS_CASES["running-sidecar-and-ready-app"][0])
    assert (
        [(c.name, c.state, c.restartable) for c in info.init_containers],
        [c.name for c in info.containers],
    ) == ([("proxy", "Running", True)], ["app"])


def test_a_container_without_a_status_yet_is_still_listed() -> None:
    """Before the kubelet reports on it, a container is known from the spec alone."""
    info = PodInfo.from_pod(pod(phase="Pending"))
    assert [(c.name, c.state, c.image) for c in info.containers] == [
        ("app", "", "example.com/app:1")
    ]


@pytest.mark.parametrize(
    ("annotations", "expected"),
    [
        ({"kubectl.kubernetes.io/default-container": "app"}, "app"),
        (None, "sidecar"),
        ({"kubectl.kubernetes.io/default-container": "missing"}, "sidecar"),
    ],
)
def test_the_default_container_follows_the_annotation_when_it_names_one(
    annotations: dict[str, str] | None, expected: str
) -> None:
    """kubectl's rule: the annotated container if the pod has it, otherwise the first."""
    api_pod = pod(containers=("sidecar", "app"), annotations=annotations)
    assert PodInfo.from_pod(api_pod).default_container == expected


def test_a_pod_without_metadata_reads_as_a_nameless_pod_in_default() -> None:
    """Reading a partial object never raises; the dashboard refuses a record without a name."""
    bare = pod()
    bare.metadata = None
    info = PodInfo.from_pod(bare)
    assert (info.name, info.namespace, info.uid, info.status) == ("", "default", "", "Running")


# =============================================================================
# Node Readiness
# =============================================================================


@pytest.mark.parametrize(
    ("ready", "expected"), [("True", True), ("False", False), ("Unknown", False)]
)
def test_a_node_is_ready_only_when_its_ready_condition_is_true(ready: str, expected: bool) -> None:
    """One predicate serves the dashboard banner and `devops k8s nodes`."""
    assert node_is_ready(node("worker-1", ready)) is expected


def test_a_node_without_conditions_is_not_ready() -> None:
    """A node that has not reported yet is not counted as Ready."""
    bare = node("worker-1")
    bare.status.conditions = None
    assert node_is_ready(bare) is False


# =============================================================================
# Events
# =============================================================================

EARLIER = NOW - datetime.timedelta(minutes=10)


@pytest.mark.parametrize(
    ("api_event", "expected"),
    [
        (event("BackOff", last=NOW, event_time=EARLIER, count=7), (NOW, 7)),
        (event("Scheduled", event_time=NOW, series_count=3), (NOW, 3)),
        (event("Pulled", first=NOW), (NOW, 1)),
        (event("Created", created=NOW), (NOW, 1)),
    ],
)
def test_an_event_is_placed_and_counted_from_whichever_fields_it_has(
    api_event: Any, expected: tuple[datetime.datetime, int]
) -> None:
    """events.k8s.io/v1 writers leave last_timestamp and count empty and set the series."""
    info = PodEventInfo.from_event(api_event)
    assert (info.last_seen, info.count) == expected


def test_an_event_keeps_its_type_reason_and_message() -> None:
    """The inspector shows what the event says, not just when."""
    info = PodEventInfo.from_event(event("BackOff", kind="Warning", message="Back-off restarting"))
    assert (info.type, info.reason, info.message) == ("Warning", "BackOff", "Back-off restarting")


# =============================================================================
# Surfaces Agree
# =============================================================================

MIXED_PODS = [
    healthy_pod("api-0", "shop"),
    crashlooping_pod("exporter-0", "monitoring"),
    STATUS_CASES["container-creating"][0],
    STATUS_CASES["completed"][0],
    STATUS_CASES["running-sidecar-and-ready-app"][0],
]


def _plain(cell: str) -> str:
    return Text.from_markup(cell).plain


def test_the_dashboard_and_k8s_pods_show_the_same_status_and_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two answers for one pod would be worse than either; both now come from one port."""
    monkeypatch.setattr(data_providers, "_get_k8s_client", lambda: FakeCoreV1(pods=MIXED_PODS))
    monkeypatch.setattr(data_providers, "_k8s_context_name", lambda: "lab")
    dashboard = [
        (_plain(row[2]), _plain(row[3])) for row in k8s_rows(data_providers.fetch_k8s_status())
    ]

    service = MagicMock()
    service.list_pods.return_value = MIXED_PODS
    with patch.object(KubernetesService, "get_instance", return_value=service):
        table = _build_pods_table(None, None, all_namespaces=True)
    cli = [(_plain(row[2]), _plain(row[3])) for row in table.rows]
    assert (dashboard, cli) == (
        [
            ("Running", "1/1"),
            ("CrashLoopBackOff", "0/1"),
            ("ContainerCreating", "0/1"),
            ("Completed", "0/1"),
            ("Running", "2/2"),
        ],
        dashboard,
    )


def test_k8s_pods_colours_a_status_by_health_not_by_phase() -> None:
    """A crashlooping pod in phase Running was printed green."""
    service = MagicMock()
    service.list_pods.return_value = [healthy_pod("api-0"), crashlooping_pod("exporter-0")]
    with patch.object(KubernetesService, "get_instance", return_value=service):
        table = _build_pods_table(None, None, all_namespaces=True)
    assert [row[2] for row in table.rows] == [
        "[green]Running[/green]",
        "[red]CrashLoopBackOff[/red]",
    ]


def test_watching_pods_prints_the_reason_a_container_gives(monkeypatch: pytest.MonkeyPatch) -> None:
    """`devops k8s pods --watch` printed the phase, Running, for a crashlooping pod."""
    watcher = MagicMock()
    watcher.stream.return_value = [{"type": "MODIFIED", "object": crashlooping_pod("exporter-0")}]
    service = MagicMock()
    service.load_config.return_value = True
    with (
        patch("kubernetes.watch.Watch", return_value=watcher),
        patch.object(KubernetesService, "get_instance", return_value=service),
    ):
        result = runner.invoke(k8s_app, ["pods", "--watch", "-A"])
    assert (result.exit_code, "default/exporter-0 (CrashLoopBackOff)" in result.output) == (0, True)
