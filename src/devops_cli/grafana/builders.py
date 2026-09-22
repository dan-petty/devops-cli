"""Reusable panel builders with automatic grid layout.

The boilerplate in a hand-authored dashboard is almost entirely positional: every panel
carries an explicit `gridPos`, a unique `id`, and a repeated datasource binding. Getting
any of those wrong produces a dashboard that renders overlapping or blank, and the error
is only visible once Grafana draws it.

These builders assign ids and lay panels out automatically, so a dashboard is expressed
as the panels it contains rather than as coordinates.
"""

from __future__ import annotations

from collections.abc import Sequence

from devops_cli.config.constants import (
    CONST_GRAFANA_DASHBOARD_GRID_WIDTH,
    CONST_GRAFANA_PANEL_TYPE_ROW,
    CONST_GRAFANA_PANEL_TYPE_STAT,
    CONST_GRAFANA_PANEL_TYPE_TIMESERIES,
)
from devops_cli.config.defaults import (
    DEFAULT_GRAFANA_PANEL_HEIGHT,
    DEFAULT_GRAFANA_ROW_HEIGHT,
)
from devops_cli.grafana.schema import (
    Dashboard,
    Datasource,
    FieldConfig,
    FieldDefaults,
    GridPos,
    Legend,
    Panel,
    Target,
)


def target(expr: str, legend: str = "", ref_id: str = "A") -> Target:
    """Build a query target bound to the default datasource."""
    return Target(expr=expr, legend_format=legend, ref_id=ref_id, datasource=Datasource())


def targets(*expressions: str | tuple[str, str]) -> list[Target]:
    """Build a list of targets, assigning sequential reference ids.

    Grafana identifies targets within a panel by `refId`; duplicating one silently drops
    a series, so the ids are assigned here rather than written by hand.
    """
    built: list[Target] = []
    for index, item in enumerate(expressions):
        expr, legend = item if isinstance(item, tuple) else (item, "")
        built.append(target(expr, legend, ref_id=chr(ord("A") + index)))
    return built


def timeseries(
    title: str,
    queries: Sequence[Target],
    *,
    unit: str = "short",
    width: int = 8,
    height: int = DEFAULT_GRAFANA_PANEL_HEIGHT,
) -> Panel:
    """Build a time series panel with the project's standard styling."""
    return Panel(
        title=title,
        type=CONST_GRAFANA_PANEL_TYPE_TIMESERIES,
        targets=list(queries),
        datasource=Datasource(),
        grid_pos=GridPos(h=height, w=width),
        field_config=FieldConfig(
            defaults=FieldDefaults(
                custom={
                    "axisCenteredZero": False,
                    "drawStyle": "line",
                    "lineInterpolation": "smooth",
                },
                unit=unit,
            )
        ),
        options={"legend": Legend().model_dump(by_alias=True)},
    )


def stat(
    title: str,
    queries: Sequence[Target],
    *,
    unit: str = "short",
    width: int = 4,
    height: int = DEFAULT_GRAFANA_PANEL_HEIGHT,
) -> Panel:
    """Build a single-value stat panel."""
    return Panel(
        title=title,
        type=CONST_GRAFANA_PANEL_TYPE_STAT,
        targets=list(queries),
        datasource=Datasource(),
        grid_pos=GridPos(h=height, w=width),
        field_config=FieldConfig(defaults=FieldDefaults(unit=unit)),
        options={"colorMode": "value", "graphMode": "area"},
    )


def row(title: str) -> Panel:
    """Build a full-width layout row separating dashboard sections."""
    return Panel(
        title=title,
        type=CONST_GRAFANA_PANEL_TYPE_ROW,
        collapsed=False,
        grid_pos=GridPos(h=DEFAULT_GRAFANA_ROW_HEIGHT, w=CONST_GRAFANA_DASHBOARD_GRID_WIDTH),
    )


def layout(panels: Sequence[Panel]) -> list[Panel]:
    """Assign grid positions and ids, flowing panels left to right.

    A panel that does not fit the remaining width of the current line wraps to the next,
    and a row always starts a fresh line at full width. This is what removes hand-written
    coordinates, which are the most common source of a visually broken dashboard.
    """
    positioned: list[Panel] = []
    cursor_x = 0
    cursor_y = 0
    line_height = 0

    for index, panel in enumerate(panels, start=1):
        width = min(panel.grid_pos.w, CONST_GRAFANA_DASHBOARD_GRID_WIDTH)

        if panel.is_row or cursor_x + width > CONST_GRAFANA_DASHBOARD_GRID_WIDTH:
            cursor_y += line_height
            cursor_x = 0
            line_height = 0

        placed = panel.model_copy(
            update={
                "id": index,
                "grid_pos": GridPos(h=panel.grid_pos.h, w=width, x=cursor_x, y=cursor_y),
            }
        )
        positioned.append(placed)

        if panel.is_row:
            cursor_y += panel.grid_pos.h
            cursor_x = 0
            line_height = 0
            continue

        cursor_x += width
        line_height = max(line_height, panel.grid_pos.h)

    return positioned


def dashboard(
    uid: str,
    title: str,
    panels: Sequence[Panel],
    *,
    tags: Sequence[str] = (),
    refresh: str = "30s",
) -> Dashboard:
    """Assemble a dashboard, laying its panels out automatically."""
    return Dashboard(
        uid=uid,
        title=title,
        tags=list(tags),
        refresh=refresh,
        panels=layout(panels),
    )


__all__ = [
    "dashboard",
    "layout",
    "row",
    "stat",
    "target",
    "targets",
    "timeseries",
]
