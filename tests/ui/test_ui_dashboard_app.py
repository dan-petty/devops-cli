"""Tests for Textual DashboardApp headless execution and lifecycle."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from textual.widgets import ContentSwitcher, Static, TabbedContent

from devops_cli.ui.dashboard import DashboardApp, HelpScreen
from devops_cli.ui.data_providers import TelemetrySummary

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.mark.usefixtures("empty_docker_engine")
async def test_textual_dashboard_app_lifecycle() -> None:
    """DashboardApp initializes, mounts header, tabs, and footer, and handles tab switching."""
    app = DashboardApp()
    async with app.run_test() as pilot:
        assert app.title == "DevOps CLI — Workstation Dashboard"
        assert app.is_running

        tabs = app.query_one(TabbedContent)
        assert tabs is not None
        assert app.is_mounted(tabs)

        await pilot.press("2")
        await pilot.pause()
        assert tabs.active == "tab-docker"

        await pilot.press("3")
        await pilot.pause()
        assert tabs.active == "tab-telemetry"

        await pilot.press("4")
        await pilot.pause()
        assert tabs.active == "tab-valkey"

        await pilot.press("1")
        await pilot.pause()
        assert tabs.active == "tab-k8s"

        await pilot.press("r")
        await pilot.pause()

        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)


@pytest.mark.usefixtures("empty_docker_engine")
async def test_the_dashboard_telemetry_tab_renders_telemetry_panel_and_opens_modal() -> None:
    """The dashboard composes TelemetryPanel under tab-telemetry and opens trace modal."""
    from devops_cli.ui.state import DomainSnapshot
    from devops_cli.ui.waterfall_modal import TraceWaterfallModal
    from devops_cli.ui.widgets import TelemetryPanel

    app = DashboardApp(initial_tab="tab-telemetry", refresh_interval=0)
    async with app.run_test() as pilot:
        panel = app.query_one(TelemetryPanel)
        assert panel is not None
        assert panel.id == "panel-telemetry"

        sample = TelemetrySummary(
            latency_samples=[15.0, 25.0],
            token_throughput_samples=[120.0],
            cache_hit_ratio=0.8,
            recent_traces=[
                {
                    "trace_id": "00112233445566778899aabbccddeeff",
                    "root_name": "ai.analyze",
                    "duration_ms": 100.0,
                    "span_count": 1,
                    "status": "OK",
                    "spans": [
                        {
                            "traceId": "00112233445566778899aabbccddeeff",
                            "spanId": "0011223344556677",
                            "name": "ai.analyze",
                            "startTimeUnixNano": "1000000000000000000",
                            "endTimeUnixNano": "1000000000100000000",
                            "status": {"code": "STATUS_CODE_OK"},
                        }
                    ],
                }
            ],
        )
        app.apply_snapshot(DomainSnapshot(domain="telemetry", data=sample))
        await pilot.pause()

        await pilot.press("w")
        await pilot.pause()
        assert any(isinstance(s, TraceWaterfallModal) for s in app.screen_stack)

        await pilot.press("escape")
        await pilot.pause()
        assert not any(isinstance(s, TraceWaterfallModal) for s in app.screen_stack)


@pytest.mark.usefixtures("empty_docker_engine")
async def test_the_dashboard_shows_four_domain_tabs_and_the_logs_tab() -> None:
    """The dashboard holds no AI Review tab: `devops review findings --details` shows findings."""
    app = DashboardApp()
    async with app.run_test():
        tabs = app.query_one("#dashboard-tabs", TabbedContent)
        shown = [pane.id for pane in tabs.get_child_by_type(ContentSwitcher).children]

    assert shown == ["tab-k8s", "tab-docker", "tab-telemetry", "tab-valkey", "tab-logs"]


@pytest.mark.usefixtures("empty_docker_engine")
async def test_the_help_screen_numbers_the_four_domain_tabs_and_lists_no_finding_key() -> None:
    """Help names tab 4 as Valkey, and it lists no key for the finding detail pane."""
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        app.push_screen(HelpScreen())
        await pilot.pause()
        help_text = str(app.screen.query_one("#help-body", Static).content)

    assert (
        "1=Kubernetes  2=Docker  3=Telemetry  4=Valkey Cache" in help_text,
        "finding" in help_text,
    ) == (
        True,
        False,
    )


@pytest.mark.usefixtures("empty_docker_engine")
async def test_dashboard_refresh_before_mount_does_not_fail_worker() -> None:
    """A panel update before the panel is mounted is deferred or dropped, never failing the worker."""
    from devops_cli.ui.state import DomainSnapshot
    from devops_cli.ui.widgets import DockerPanel, DomainPanel, K8sPanel

    panels: list[Any] = [
        DomainPanel("telemetry"),
        DomainPanel("valkey"),
        K8sPanel("k8s"),
        DockerPanel("docker"),
    ]
    snapshots = [DomainSnapshot(domain=p.domain) for p in panels]
    for p, s in zip(panels, snapshots, strict=True):
        p.apply(s)

    assert (
        all(p._pending_snapshot is s for p, s in zip(panels, snapshots, strict=True)),
        all(not p.is_mounted for p in panels),
    ) == (True, True)

    app = DashboardApp(refresh_interval=0)
    for s in snapshots:
        app.apply_snapshot(s)

    from textual.worker import WorkerState

    async with app.run_test() as pilot:
        await pilot.pause()
        assert (
            app.is_running,
            any(w.state == WorkerState.ERROR for w in app.workers),
        ) == (True, False)


@pytest.mark.parametrize(
    ("refresh_interval", "timer_started"),
    [pytest.param(5, True, id="positive-interval"), pytest.param(0, False, id="zero-interval")],
)
def test_the_dashboard_starts_its_refresh_timer_only_for_a_positive_interval(
    refresh_interval: int, timer_started: bool
) -> None:
    """A zero or negative refresh interval disables periodic dashboard refreshes."""
    tui = DashboardApp(refresh_interval=refresh_interval)
    with (
        patch.object(tui, "action_refresh_data") as refresh,
        patch.object(tui, "set_interval") as set_interval,
    ):
        tui.on_mount()

    assert (refresh.call_count, set_interval.call_count == 1) == (
        1,
        timer_started,
    )
