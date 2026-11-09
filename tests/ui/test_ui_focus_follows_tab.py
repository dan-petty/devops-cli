"""Tests for Focus Follows the Tab behaviour in reactive dashboard."""

from __future__ import annotations

from collections.abc import Callable

from textual.widgets import DataTable, TabbedContent

from devops_cli.ui.dashboard import DashboardApp
from tests.support.ui import (
    _containers,
    _loaded,
)


async def test_keys_reach_the_docker_table_without_focusing_by_hand(
    patched_fetchers: Callable[..., None],
) -> None:
    """At startup the tab strip held focus, so the active table ignored its keys."""
    patched_fetchers(docker=lambda: _containers(5))
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        table = app.query_one("#docker-table", DataTable)
        await pilot.press("down")
        moved = table.cursor_row
        await pilot.press("2")
        await pilot.pause()
        telemetry_table = app.query_one("#telemetry-table", DataTable)
        await pilot.press("down")
        telemetry_moved = telemetry_table.cursor_row
        await pilot.press("1", "down")
        assert (moved, telemetry_moved, table.cursor_row) == (1, 1, 2)


async def test_another_tab_takes_focus_on_tab_switch(
    patched_fetchers: Callable[..., None],
) -> None:
    """A hidden table kept focus, so a tab switch bounced back."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        await pilot.press("2")
        await pilot.pause()
        assert (
            app.query_one(TabbedContent).active,
            app.focused.id if app.focused else None,
        ) == ("tab-telemetry", "telemetry-table")
        await pilot.press("3")
        await pilot.pause()
        assert (
            app.query_one(TabbedContent).active,
            app.focused.id if app.focused else None,
        ) == ("tab-valkey", "valkey-table")
