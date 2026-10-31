"""Tests for Keeping Place Across Refreshes behaviour in reactive dashboard."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pytest
from textual.widgets import DataTable, Static

from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.data_providers import (
    DockerSummary,
    K8sSummary,
)
from devops_cli.ui.state import DashboardState, DomainSnapshot
from devops_cli.ui.widgets import K8sPanel
from tests.support.ui import (
    _containers,
    _loaded,
    _pod,
    _pods,
    _refresh,
    _wide_pods,
)


def _place(table: DataTable[Any]) -> tuple[int, str | None]:
    """Return the cursor row and the key of the row it highlights."""
    return table.cursor_row, table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value


@pytest.mark.parametrize(("tab", "table_id"), [("1", "k8s-table"), ("2", "docker-table")])
async def test_a_refresh_with_unchanged_data_keeps_the_highlighted_row(
    patched_fetchers: Callable[..., None], tab: str, table_id: str
) -> None:
    """The cursor jumped back to the first row on every refresh, every five seconds."""
    patched_fetchers(k8s=lambda: _pods(3), docker=lambda: _containers(3))
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        await pilot.press(tab)
        table = app.query_one(f"#{table_id}", DataTable)
        table.focus()
        table.move_cursor(row=2)
        await pilot.pause()
        before = _place(table)
        await _refresh(pilot, app)
        assert (before[0], _place(table)) == (2, before)


@pytest.mark.parametrize(
    ("tab", "table_id", "size", "row", "scroll"),
    [
        ("1", "k8s-table", (100, 24), 12, (0, 10)),
        ("1", "k8s-table", (100, 24), 2, (0, 20)),
        ("1", "k8s-table", (80, 24), 20, (30, 10)),
    ],
)
async def test_a_refresh_keeps_the_cursor_and_scroll_of_a_long_table(
    patched_fetchers: Callable[..., None],
    tab: str,
    table_id: str,
    size: tuple[int, int],
    row: int,
    scroll: tuple[int, int],
) -> None:
    """The view stays where it was, including when the cursor is scrolled out of sight.

    A table wider than the screen is read scrolled to the right, so a refresh must not snap
    the view back to the left edge either.
    """
    patched_fetchers(k8s=lambda: _pods(50) if size[0] > 80 else _wide_pods(50))
    app = DashboardApp(refresh_interval=0)
    async with app.run_test(size=size) as pilot:
        await _loaded(pilot, app)
        await pilot.press(tab)
        table = app.query_one(f"#{table_id}", DataTable)
        table.focus()
        table.move_cursor(row=row)
        await pilot.pause()
        table.scroll_to(x=scroll[0], y=scroll[1], animate=False)
        await pilot.pause()
        before = (table.cursor_row, table.scroll_x, table.scroll_y)
        await _refresh(pilot, app)
        assert (before, (table.cursor_row, table.scroll_x, table.scroll_y)) == (
            (row, *scroll),
            (row, *scroll),
        )


async def test_a_table_on_a_hidden_tab_keeps_its_place_through_a_refresh(
    patched_fetchers: Callable[..., None],
) -> None:
    """Every table refreshes, not just the visible one, so a hidden one must not reset."""
    patched_fetchers(k8s=lambda: _pods(50))
    app = DashboardApp(refresh_interval=0)
    async with app.run_test(size=(100, 24)) as pilot:
        await _loaded(pilot, app)
        table = app.query_one("#k8s-table", DataTable)
        table.focus()
        table.move_cursor(row=30)
        await pilot.pause()
        before = (table.cursor_row, table.scroll_y)
        await pilot.press("2")
        await _refresh(pilot, app)
        await pilot.press("1")
        await pilot.pause()
        assert (before[1] > 0, (table.cursor_row, table.scroll_y)) == (True, before)


@pytest.mark.parametrize(
    ("remaining", "expected"),
    [
        (["pod-00", "pod-01", "pod-03"], (2, 3)),
        (["pod-00", "pod-01"], (1, 2)),
        ([], (0, 0)),
    ],
)
async def test_a_vanished_record_leaves_the_cursor_at_its_index(
    patched_fetchers: Callable[..., None], remaining: list[str], expected: tuple[int, int]
) -> None:
    """The cursor keeps its index, moved back to the last row if the table is now shorter."""
    patched_fetchers(k8s=lambda: _pods(3))
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        table = app.query_one("#k8s-table", DataTable)
        table.move_cursor(row=2)
        await pilot.pause()
        summary = K8sSummary(connected=True, pods=[_pod(name) for name in remaining])
        app.query_one("#panel-k8s", K8sPanel).apply(
            DomainSnapshot(domain="k8s", data=summary, updated_at=time.time())
        )
        await pilot.pause()
        assert (table.cursor_row, table.row_count) == expected


async def test_containers_without_an_id_are_separate_rows(
    patched_fetchers: Callable[..., None],
) -> None:
    """Containers share the empty-id fallback, which must not collide into an error banner."""
    blank = {"id": "", "name": "unknown", "image": "none", "status": "created"}
    patched_fetchers(
        docker=lambda: DockerSummary(connected=True, containers=[dict(blank), dict(blank)])
    )
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        await _refresh(pilot, app)
        banner = str(app.query_one("#docker-banner", Static).render())
        assert (
            app.query_one("#docker-table", DataTable).row_count,
            state.failed_domains(),
            "render failed" in banner,
        ) == (2, [], False)
