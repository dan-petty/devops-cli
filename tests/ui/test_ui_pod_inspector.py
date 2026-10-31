"""Tests for Pod Inspector behaviour in reactive dashboard."""

from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Any

import pytest
from textual.widgets import DataTable, Static

import devops_cli.ui.data_providers as data_providers
from devops_cli.config.defaults import DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS
from devops_cli.models.k8s import PodEventInfo, PodInfo
from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.data_providers import (
    K8sSummary,
)
from devops_cli.ui.pod_inspector import PodInspector
from devops_cli.ui.projections import (
    pod_container_rows,
    pod_event_rows,
)
from tests.support.fakes.kubernetes import (
    NOW,
    FakeCoreV1,
    crashlooping_pod,
    event,
    pod,
    running,
    terminated,
)
from tests.support.fakes.kubernetes import status as container_status
from tests.support.ui import (
    _loaded,
)

EVENT_FIELD_SELECTOR = (
    "involvedObject.kind=Pod,involvedObject.name=exporter-0,"
    "involvedObject.uid=uid-monitoring-exporter-0"
)


def _inspected() -> K8sSummary:
    return K8sSummary(
        connected=True, pods=[PodInfo.from_pod(crashlooping_pod("exporter-0", "monitoring"))]
    )


def _events() -> list[Any]:
    """25 events a minute apart, plus a newest one written through events.k8s.io/v1."""
    old = [
        event(f"Old{index:02d}", last=NOW - datetime.timedelta(minutes=30 - index), count=1)
        for index in range(25)
    ]
    return [*old, event("Series", event_time=NOW, series_count=9)]


async def _inspect(pilot: Any, app: DashboardApp) -> PodInspector:
    """Open the inspector on the highlighted pod and wait for its events call to finish."""
    await _loaded(pilot, app)
    await pilot.press("e")
    await pilot.pause()
    screen = app.screen
    assert isinstance(screen, PodInspector)
    await screen.workers.wait_for_complete()
    await pilot.pause()
    return screen


def _cells(screen: PodInspector, table_id: str) -> list[list[str]]:
    table = screen.query_one(table_id, DataTable)
    return [[str(cell) for cell in table.get_row(key)] for key in table.rows]


async def test_e_inspects_the_pod_from_its_record_and_its_newest_events(
    patched_fetchers: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Containers come from the snapshot; the only API call is for the pod's own events."""
    patched_fetchers(k8s=_inspected)
    core = FakeCoreV1(events=_events())
    monkeypatch.setattr(data_providers, "_get_k8s_client", lambda: core)
    app = DashboardApp(refresh_interval=0)
    async with app.run_test(size=(160, 50)) as pilot:
        screen = await _inspect(pilot, app)
        events = _cells(screen, "#inspector-events")
        assert (
            _cells(screen, "#inspector-containers"),
            len(events),
            events[0][1:4:2],
            [row[1] for row in events[1:3]],
            core.calls,
        ) == (
            [
                [
                    "app",
                    "example.com/app:1",
                    "no",
                    "86",
                    "Waiting: CrashLoopBackOff",
                    "Error (exit 1)",
                ]
            ],
            20,
            ["Series", "9"],
            ["Old24", "Old23"],
            [
                (
                    "list_namespaced_event",
                    {
                        "namespace": "monitoring",
                        "field_selector": EVENT_FIELD_SELECTOR,
                        "_request_timeout": DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
                    },
                )
            ],
        )


async def test_a_failed_events_call_is_shown_in_the_inspector(
    patched_fetchers: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 403 on events is reported in the dialog, and the dashboard carries on."""
    from kubernetes.client.exceptions import ApiException  # type: ignore[import-untyped]

    patched_fetchers(k8s=_inspected)
    core = FakeCoreV1(events=ApiException(status=403, reason="Forbidden"))
    monkeypatch.setattr(data_providers, "_get_k8s_client", lambda: core)
    app = DashboardApp(refresh_interval=0)
    async with app.run_test(size=(160, 50)) as pilot:
        screen = await _inspect(pilot, app)
        status = str(screen.query_one("#inspector-events-status", Static).render())
        await pilot.press("escape")
        await pilot.pause()
        assert "403 Forbidden" in status
        assert app.is_running
        assert not isinstance(app.screen, PodInspector)


def test_container_rows_show_state_and_last_termination() -> None:
    """Init containers are listed too, marked as such.

    A previous run that ended without a reason, as one killed by a signal can, is named
    by its state.
    """
    info = PodInfo.from_pod(
        pod(
            statuses=[container_status("app", running(), restarts=1, last=terminated(137))],
            init_containers=("migrate",),
            init_statuses=[container_status("migrate", terminated(0, "Completed"))],
        )
    )
    assert pod_container_rows(info) == [
        ("app", "example.com/app:1", "no", "1", "Running", "Terminated (exit 137)"),
        ("migrate (init)", "example.com/migrate:1", "no", "0", "Terminated: Completed", "—"),
    ]


def test_event_rows_escape_cluster_text_and_age_from_last_seen() -> None:
    """An event message is cluster text: it must not be read as markup."""
    rows = pod_event_rows(
        [PodEventInfo(type="Warning", reason="BackOff", message="see [bold]x[/bold]", count=3)]
    )
    assert rows == [("Warning", "BackOff", "—", "3", "see \\[bold]x\\[/bold]")]
