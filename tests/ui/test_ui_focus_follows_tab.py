"""Tests for Focus Follows the Tab behaviour in reactive dashboard."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from textual.widgets import DataTable, TabbedContent

import devops_cli.ui.dashboard as dashboard_module
from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.pod_inspector import PodInspector
from devops_cli.ui.widgets import LogPane
from tests.support.ui import (
    _loaded,
    _numbered_lines,
    _pods,
    _settle,
)


async def test_keys_reach_the_pod_table_and_the_log_pane_without_focusing_by_hand(
    patched_fetchers: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """At startup the tab strip held focus, so the pod table and log pane ignored their keys."""
    patched_fetchers(k8s=lambda: _pods(5))
    monkeypatch.setattr(dashboard_module, "pod_log_source", _numbered_lines(300))
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        table = app.query_one("#k8s-table", DataTable)
        await pilot.press("down")
        moved = table.cursor_row
        await pilot.press("enter")
        pane = app.query_one("#log-pane", LogPane)
        await _settle(pilot, lambda: pane.buffer.total_appended >= 300)
        await pilot.press("pageup")
        paged = (app.query_one(TabbedContent).active, pane.buffer.following, pane.buffer.offset)
        await pilot.press("end")
        followed = pane.buffer.following
        await pilot.press("1", "down")
        assert (moved, paged[:2], paged[2] < pane.buffer.offset, followed, table.cursor_row) == (
            1,
            ("tab-logs", False),
            True,
            True,
            2,
        )


async def test_another_tab_takes_focus_so_the_pod_keys_stay_on_the_kubernetes_tab(
    patched_fetchers: Callable[..., None],
) -> None:
    """A hidden pod table kept focus, so a tab switch bounced back and `e` acted unseen."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        await pilot.press("3", "e")
        await pilot.pause()
        assert (
            app.query_one(TabbedContent).active,
            app.focused.id if app.focused else None,
        ) == ("tab-telemetry", "telemetry-table")
        assert not isinstance(app.screen, PodInspector)
