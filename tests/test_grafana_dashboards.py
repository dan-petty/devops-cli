"""Unit tests for declarative Grafana dashboard schema, builders, and linting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.grafana import app as grafana_app
from devops_cli.grafana import (
    dashboard,
    layout,
    lint_dashboard,
    lint_dashboard_file,
    load_dashboard,
    row,
    stat,
    targets,
    timeseries,
)
from devops_cli.grafana.schema import Dashboard, Datasource, GridPos, Panel, Target

runner = CliRunner()

_REPO_DASHBOARDS = Path(__file__).resolve().parents[1] / "k8s" / "monitoring" / "dashboards"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Grid geometry
# ─────────────────────────────────────────────────────────────────────────────


def test_grid_position_reports_its_edges() -> None:
    """A panel knows where it ends, not just where it starts."""
    pos = GridPos(h=8, w=12, x=6, y=4)
    assert (pos.right, pos.bottom) == (18, 12)


def test_adjacent_panels_do_not_overlap() -> None:
    """Panels sharing an edge are adjacent, not overlapping."""
    left = GridPos(h=8, w=12, x=0, y=0)
    right = GridPos(h=8, w=12, x=12, y=0)
    assert left.overlaps(right) is False


def test_intersecting_panels_overlap() -> None:
    """Panels sharing any cell collide, and one would be hidden."""
    first = GridPos(h=8, w=12, x=0, y=0)
    second = GridPos(h=8, w=12, x=6, y=0)
    assert (first.overlaps(second), second.overlaps(first)) == (True, True)


def test_vertically_separated_panels_do_not_overlap() -> None:
    """Panels on different rows never collide."""
    top = GridPos(h=8, w=24, x=0, y=0)
    bottom = GridPos(h=8, w=24, x=0, y=8)
    assert top.overlaps(bottom) is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. Automatic layout
# ─────────────────────────────────────────────────────────────────────────────


def test_layout_flows_panels_left_to_right() -> None:
    """Panels fill a line before starting the next."""
    placed = layout([timeseries(f"P{i}", targets("up"), width=8) for i in range(3)])
    assert [(p.grid_pos.x, p.grid_pos.y) for p in placed] == [(0, 0), (8, 0), (16, 0)]


def test_layout_wraps_panels_that_exceed_the_line() -> None:
    """A panel that will not fit wraps to the next line rather than overflowing."""
    placed = layout([timeseries(f"P{i}", targets("up"), width=12) for i in range(3)])
    assert [(p.grid_pos.x, p.grid_pos.y) for p in placed] == [(0, 0), (12, 0), (0, 8)]


def test_layout_assigns_unique_sequential_ids() -> None:
    """Every panel receives a distinct id, which Grafana keys links by."""
    placed = layout([timeseries(f"P{i}", targets("up")) for i in range(5)])
    ids = [p.id for p in placed]
    assert (ids, len(set(ids))) == ([1, 2, 3, 4, 5], 5)


def test_rows_start_a_fresh_full_width_line() -> None:
    """A row separates sections, so following panels begin beneath it."""
    placed = layout(
        [
            timeseries("Before", targets("up"), width=8),
            row("Section"),
            timeseries("After", targets("up"), width=8),
        ]
    )
    before, section, after = placed

    assert (before.grid_pos.y, section.grid_pos.y) == (0, 8)
    assert (after.grid_pos.x, after.grid_pos.y) == (0, 9)
    assert section.grid_pos.w == 24


def test_layout_clamps_oversized_panels_to_the_grid() -> None:
    """A panel wider than the grid is clamped rather than silently clipped by Grafana."""
    placed = layout([timeseries("Wide", targets("up"), width=40)])
    assert placed[0].grid_pos.w == 24


def test_laid_out_panels_never_overlap() -> None:
    """Automatic layout cannot produce a colliding dashboard.

    Hand-written coordinates are the most common cause of a visually broken dashboard;
    this is the property that removes the possibility.
    """
    panels = [timeseries(f"P{i}", targets("up"), width=w) for i, w in enumerate([8, 8, 12, 6, 24])]
    placed = [p for p in layout(panels) if not p.is_row]

    for index, panel in enumerate(placed):
        for other in placed[index + 1 :]:
            assert not panel.grid_pos.overlaps(other.grid_pos), (
                f"{panel.title} overlaps {other.title}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Builders
# ─────────────────────────────────────────────────────────────────────────────


def test_targets_receive_sequential_reference_ids() -> None:
    """Grafana identifies targets by refId; duplicating one drops a series."""
    built = targets("up", "down", ("rate(x[5m])", "legend"))
    assert [t.ref_id for t in built] == ["A", "B", "C"]
    assert built[2].legend_format == "legend"


def test_builders_bind_the_default_datasource() -> None:
    """Every generated panel and target carries a datasource binding."""
    panel = timeseries("CPU", targets("up"))
    assert panel.datasource is not None
    assert panel.targets[0].datasource.type == "prometheus"


def test_stat_and_timeseries_produce_their_panel_types() -> None:
    """Builders emit the panel type Grafana expects."""
    assert (
        timeseries("A", targets("up")).type,
        stat("B", targets("up")).type,
        row("C").type,
    ) == ("timeseries", "stat", "row")


def test_row_is_not_a_visualisation() -> None:
    """A row is layout, not a panel with data."""
    assert (row("Section").is_row, timeseries("A", targets("up")).is_row) == (True, False)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Serialisation fidelity
# ─────────────────────────────────────────────────────────────────────────────


def test_serialisation_emits_grafana_field_names() -> None:
    """Output uses Grafana's camelCase keys, not the Python field names."""
    built = dashboard("uid-1", "Test", [timeseries("CPU", targets("up", ""))])
    payload = built.to_grafana_json()

    assert "schemaVersion" in payload
    assert "gridPos" in payload["panels"][0]
    assert "refId" in payload["panels"][0]["targets"][0]
    assert "grid_pos" not in payload["panels"][0]


def test_serialisation_omits_unset_optional_fields() -> None:
    """A generated dashboard carries no null keys a hand-authored one would lack."""
    payload = dashboard("uid-1", "Test", [row("Section")]).to_grafana_json()
    assert "datasource" not in payload["panels"][0]


def test_generated_dashboard_round_trips_through_the_schema() -> None:
    """Serialised output re-parses to an equivalent dashboard."""
    original = dashboard("uid-1", "Round Trip", [timeseries("CPU", targets("up"))])
    reparsed = Dashboard.model_validate(original.to_grafana_json())

    assert reparsed.to_grafana_json() == original.to_grafana_json()


# ─────────────────────────────────────────────────────────────────────────────
# 5. Linting: real dashboards must pass
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "dashboard_file", sorted(_REPO_DASHBOARDS.glob("*.json")), ids=lambda p: p.name
)
def test_repository_dashboards_lint_clean(dashboard_file: Path) -> None:
    """The dashboards actually shipped in this repository must lint without errors.

    These are hand-authored and known to render, so any error here is a false positive in
    the linter rather than a defect in the dashboard.
    """
    report = lint_dashboard_file(dashboard_file)
    assert report.passed, f"{dashboard_file.name}: {[i.message for i in report.errors]}"


def test_generated_dashboards_lint_clean() -> None:
    """Anything the builders produce is valid by construction."""
    built = dashboard(
        "generated",
        "Generated",
        [
            row("Overview"),
            timeseries("Requests", targets("sum(rate(http_total[5m]))")),
            stat("Errors", targets("sum(rate(errors_total[5m]))")),
        ],
    )
    assert lint_dashboard(built).passed is True


# ─────────────────────────────────────────────────────────────────────────────
# 6. Linting: defects are caught
# ─────────────────────────────────────────────────────────────────────────────


def _panel(title: str, pos: GridPos, expr: str = "up", panel_id: int = 1) -> Panel:
    """Build a minimal visualisation panel."""
    return Panel(
        id=panel_id,
        title=title,
        grid_pos=pos,
        datasource=Datasource(),
        targets=[Target(expr=expr)],
    )


def test_missing_uid_is_an_error() -> None:
    """Grafana addresses dashboards by uid; without one it cannot be provisioned."""
    report = lint_dashboard(Dashboard(uid="", title="Untitled"))
    assert any("uid" in issue.message for issue in report.errors)


def test_duplicate_panel_ids_are_reported() -> None:
    """A duplicate id makes panel links target the wrong panel."""
    report = lint_dashboard(
        Dashboard(
            uid="u",
            title="T",
            panels=[
                _panel("A", GridPos(h=8, w=12, x=0, y=0), panel_id=7),
                _panel("B", GridPos(h=8, w=12, x=12, y=0), panel_id=7),
            ],
        )
    )
    assert any("used by 2 panels" in issue.message for issue in report.errors)


def test_overlapping_panels_are_reported() -> None:
    """Overlapping panels hide one another when rendered."""
    report = lint_dashboard(
        Dashboard(
            uid="u",
            title="T",
            panels=[
                _panel("A", GridPos(h=8, w=12, x=0, y=0), panel_id=1),
                _panel("B", GridPos(h=8, w=12, x=6, y=0), panel_id=2),
            ],
        )
    )
    assert any("overlaps" in issue.message for issue in report.errors)


def test_panel_beyond_the_grid_is_reported() -> None:
    """A panel wider than 24 columns is clipped by Grafana without warning."""
    report = lint_dashboard(
        Dashboard(uid="u", title="T", panels=[_panel("Wide", GridPos(h=8, w=30, x=0, y=0))])
    )
    assert any("past the 24-column grid" in issue.message for issue in report.errors)


def test_malformed_promql_in_a_target_is_reported() -> None:
    """Dashboard queries are validated with the same checker the CLI uses.

    A query rejected at the command line must not silently ship inside a dashboard.
    """
    report = lint_dashboard(
        Dashboard(
            uid="u",
            title="T",
            panels=[_panel("Broken", GridPos(h=8, w=12, x=0, y=0), expr="rate(x[5m")],
        )
    )
    assert any("Invalid PromQL" in issue.message for issue in report.errors)


def test_duplicate_target_ref_ids_are_reported() -> None:
    """Two targets sharing a refId means one series is silently dropped."""
    panel = Panel(
        id=1,
        title="Dup",
        grid_pos=GridPos(h=8, w=12, x=0, y=0),
        datasource=Datasource(),
        targets=[Target(expr="up", ref_id="A"), Target(expr="down", ref_id="A")],
    )
    report = lint_dashboard(Dashboard(uid="u", title="T", panels=[panel]))
    assert any("Duplicate target refId" in issue.message for issue in report.errors)


def test_panel_without_targets_or_datasource_warns() -> None:
    """An unbound panel renders blank, which is worth flagging but not fatal."""
    report = lint_dashboard(
        Dashboard(
            uid="u",
            title="T",
            panels=[Panel(id=1, title="Empty", grid_pos=GridPos(h=8, w=12, x=0, y=0))],
        )
    )
    assert (report.passed, len(report.warnings)) == (True, 2)


def test_rows_are_exempt_from_target_and_overlap_checks() -> None:
    """Rows carry no queries and span the grid by design."""
    report = lint_dashboard(Dashboard(uid="u", title="T", panels=[row("Section")]))
    assert report.passed is True


# ─────────────────────────────────────────────────────────────────────────────
# 7. Loading and CLI
# ─────────────────────────────────────────────────────────────────────────────


def test_export_wrapped_dashboards_are_unwrapped() -> None:
    """Grafana exports nest the dashboard under a `dashboard` key; both forms load."""
    body = {"uid": "wrapped", "title": "Wrapped", "panels": []}
    assert load_dashboard({"dashboard": body}).uid == "wrapped"
    assert load_dashboard(body).uid == "wrapped"


def test_unparseable_file_reports_an_error(tmp_path: Path) -> None:
    """A corrupt dashboard file is reported rather than raising."""
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")

    report = lint_dashboard_file(broken)
    assert (report.passed, "Could not parse" in report.errors[0].message) == (False, True)


def test_non_object_dashboard_reports_an_error(tmp_path: Path) -> None:
    """A JSON array is not a dashboard."""
    listed = tmp_path / "list.json"
    listed.write_text("[1, 2, 3]", encoding="utf-8")
    assert lint_dashboard_file(listed).passed is False


def test_cli_lints_the_repository_dashboards() -> None:
    """The lint command reports a clean run over the shipped dashboards."""
    result = runner.invoke(grafana_app, ["dashboards", "lint", str(_REPO_DASHBOARDS)])
    assert result.exit_code == 0
    assert "0 error(s)" in result.output


def test_cli_exits_non_zero_on_errors(tmp_path: Path) -> None:
    """A dashboard with errors fails the command, so CI can gate on it."""
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "uid": "",
                "title": "Bad",
                "panels": [
                    {
                        "id": 1,
                        "title": "Broken",
                        "type": "timeseries",
                        "gridPos": {"h": 8, "w": 30, "x": 0, "y": 0},
                        "datasource": {"type": "prometheus", "uid": "prometheus"},
                        "targets": [{"expr": "rate(x[5m", "refId": "A"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(grafana_app, ["dashboards", "lint", str(bad)])
    assert result.exit_code == 1
    assert "Invalid PromQL" in result.output


def test_cli_reports_a_missing_path(tmp_path: Path) -> None:
    """A path that does not exist fails with an actionable message."""
    result = runner.invoke(grafana_app, ["dashboards", "lint", str(tmp_path / "absent")])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_cli_json_output_is_machine_readable() -> None:
    """Reports serialise for downstream tooling."""
    result = runner.invoke(grafana_app, ["dashboards", "lint", str(_REPO_DASHBOARDS), "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert len(payload) == len(list(_REPO_DASHBOARDS.glob("*.json")))


def test_cli_supports_dry_run() -> None:
    """Linting can be previewed without reading dashboards."""
    result = runner.invoke(
        grafana_app,
        ["dashboards", "lint", str(_REPO_DASHBOARDS)],
        env={"DEVOPS_CLI_DRY_RUN": "true"},
    )
    assert result.exit_code == 0
    assert "lint_grafana_dashboards" in result.output
