"""Tests for Kubernetes Panel: Stable Selection behaviour in reactive dashboard."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from textual.widgets import DataTable, Select

from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.data_providers import (
    K8sSummary,
)
from tests.support.ui import (
    _cluster,
    _loaded,
    _pod,
    _refresh,
    _shown,
)


@pytest.mark.parametrize(
    ("removed", "expected_row", "expected_pod"),
    [("web-00", 39, "web-27"), ("web-27", 40, "web-28")],
)
async def test_the_cursor_stays_on_its_pod_or_the_nearest_row(
    patched_fetchers: Callable[..., None], removed: str, expected_row: int, expected_pod: str
) -> None:
    """Row 40 of 63 went back to row 0 on every snapshot; now it follows the pod."""
    cluster = {"summary": _cluster()}
    patched_fetchers(k8s=lambda: cluster["summary"])
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        table = app.query_one("#k8s-table", DataTable)
        table.move_cursor(row=40)
        await pilot.pause()
        before = _shown(app)[table.cursor_row]
        cluster["summary"] = _cluster(without=removed)
        await _refresh(pilot, app)
        assert (before, table.cursor_row, _shown(app)[table.cursor_row]) == (
            "web-27",
            expected_row,
            expected_pod,
        )


def _two_namespaces(*, ahead: int = 0) -> K8sSummary:
    """40 pods in alpha, then 60 in beta, listed after `ahead` pods in jobs."""
    return K8sSummary(
        connected=True,
        context="lab",
        pods=[
            *(_pod(f"j-{index:03d}", "jobs") for index in range(ahead)),
            *(_pod(f"a-{index:03d}", "alpha") for index in range(40)),
            *(_pod(f"b-{index:03d}", "beta") for index in range(60)),
        ],
    )


def _cursor_on_screen(table: DataTable[Any]) -> bool:
    """Whether the highlighted row lies inside the window the table is scrolled to."""
    rows = table.scrollable_content_region.height - table.header_height
    return table.scroll_y <= table.cursor_row < table.scroll_y + rows


async def _scrolled(pilot: Any) -> None:
    """Wait out the scrolls a redraw defers, each until after the next screen refresh (#834)."""
    for _ in range(4):
        await pilot.pause()


async def test_choosing_a_namespace_keeps_the_highlighted_pod_on_screen(
    patched_fetchers: Callable[..., None],
) -> None:
    """b-030 moved from row 70 to row 30 under the offset row 70 needed, out of sight.

    Enter and `e` then acted on a pod the operator could not see.
    """
    patched_fetchers(k8s=_two_namespaces)
    app = DashboardApp(refresh_interval=0)
    async with app.run_test(size=(120, 30)) as pilot:
        await _loaded(pilot, app)
        table = app.query_one("#k8s-table", DataTable)
        table.move_cursor(row=70)
        await _scrolled(pilot)
        before = (_shown(app)[table.cursor_row], table.scroll_y > 30, _cursor_on_screen(table))
        app.query_one("#k8s-namespace", Select).value = "beta"
        await _scrolled(pilot)
        assert (before, _shown(app)[table.cursor_row], _cursor_on_screen(table)) == (
            ("b-030", True, True),
            "b-030",
            True,
        )


async def test_pods_added_above_the_cursor_leave_its_pod_on_screen(
    patched_fetchers: Callable[..., None],
) -> None:
    """A refresh listing 30 new pods first left the highlighted pod below the window."""
    cluster = {"summary": _two_namespaces()}
    patched_fetchers(k8s=lambda: cluster["summary"])
    app = DashboardApp(refresh_interval=0)
    async with app.run_test(size=(120, 30)) as pilot:
        await _loaded(pilot, app)
        table = app.query_one("#k8s-table", DataTable)
        table.move_cursor(row=5)
        await _scrolled(pilot)
        cluster["summary"] = _two_namespaces(ahead=30)
        await _refresh(pilot, app)
        await _scrolled(pilot)
        assert (table.cursor_row, _shown(app)[table.cursor_row], _cursor_on_screen(table)) == (
            35,
            "a-005",
            True,
        )
