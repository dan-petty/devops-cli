"""Unit tests for declarative Grafana dashboard schema, builders, and linting."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.grafana import app as grafana_app
from devops_cli.config import constants
from devops_cli.grafana import (
    dashboard,
    layout,
    lint_dashboard,
    lint_dashboard_file,
    lint_dashboard_files,
    load_dashboard,
    row,
    stat,
    targets,
    timeseries,
)
from devops_cli.grafana.schema import Dashboard, Datasource, GridPos, Panel, Target
from tests.support.paths import REPO_ROOT

runner = CliRunner()

_REPO_DASHBOARDS = REPO_ROOT / "k8s" / "monitoring" / "dashboards"
_SERIES_WITH_NO_JOB_MATCHER = re.compile(r'devops_cli_[a-z0-9_]+\b(?!\{job=~"\$job")')
_JOB_VALUES = (
    'label_values({__name__=~"devops_cli_command_total|devops_cli_github_requests_total"}, job)'
)


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
    assert report.errors == [], f"{dashboard_file.name}: {[i.message for i in report.errors]}"


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


@pytest.mark.parametrize(
    ("expression", "errors"),
    [("$A + $B * 10", []), ("", ["Panel target has an empty query"])],
    ids=["filled", "empty"],
)
def test_an_expression_target_is_checked_by_its_expression(
    expression: str, errors: list[str]
) -> None:
    """A target of the Grafana expression datasource (`__expr__`) holds its query in
    `expression` and has no `expr`. Grafana evaluates it on the server from the other targets of
    the panel, as the upstream CloudNativePG dashboard does (#4994), so only an empty expression
    is an error, and it is not PromQL."""
    panel = {
        "id": 1,
        "type": "stat",
        "title": "Errors",
        "gridPos": {"h": 2, "w": 2, "x": 0, "y": 0},
        "datasource": {"type": "prometheus", "uid": "prometheus"},
        "targets": [
            {"expr": "up", "refId": "A", "hide": True},
            {"expr": "up", "refId": "B", "hide": True},
            {
                "datasource": {"type": "__expr__", "uid": "${DS_EXPRESSION}"},
                "expression": expression,
                "refId": "C",
                "type": "math",
            },
        ],
    }
    report = lint_dashboard(load_dashboard({"uid": "u", "title": "T", "panels": [panel]}))

    assert [issue.message for issue in report.errors] == errors


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


def _write_dashboards(directory: Path, uids: dict[str, str]) -> list[Path]:
    """Write one empty dashboard per file name, with the given uid."""
    for name, uid in uids.items():
        (directory / name).write_text(
            json.dumps({"uid": uid, "title": name, "panels": []}), encoding="utf-8"
        )
    return [directory / name for name in uids]


def test_dashboards_sharing_a_uid_each_name_the_other(tmp_path: Path) -> None:
    """Grafana keeps one dashboard per uid, so the second file silently overwrites the first."""
    reports = lint_dashboard_files(
        _write_dashboards(tmp_path, {"a.json": "shared", "b.json": "shared", "c.json": "own"})
    )

    assert [(r.source_file, [i.message for i in r.errors]) for r in reports] == [
        ("a.json", ["Dashboard uid 'shared' is also used by b.json; Grafana keeps only one"]),
        ("b.json", ["Dashboard uid 'shared' is also used by a.json; Grafana keeps only one"]),
        ("c.json", []),
    ]


def test_cli_fails_on_a_shared_uid_and_names_both_files(tmp_path: Path) -> None:
    """The table and `--json` both exit 1, and the error is reported under each file."""
    _write_dashboards(tmp_path, {"a.json": "shared", "b.json": "shared"})

    table = runner.invoke(grafana_app, ["dashboards", "lint", str(tmp_path)])
    as_json = runner.invoke(grafana_app, ["dashboards", "lint", str(tmp_path), "--json"])
    reports = json.loads(as_json.output)

    assert (
        table.exit_code,
        "also used by b.json" in table.output and "also used by a.json" in table.output,
        as_json.exit_code,
        [
            (report["source_file"], [issue["message"] for issue in report["issues"]])
            for report in reports
        ],
    ) == (
        1,
        True,
        1,
        [
            ("a.json", ["Dashboard uid 'shared' is also used by b.json; Grafana keeps only one"]),
            ("b.json", ["Dashboard uid 'shared' is also used by a.json; Grafana keeps only one"]),
        ],
    )


def test_cli_json_output_exits_non_zero_on_errors(tmp_path: Path) -> None:
    """`--json` gates CI the same way the table does."""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"uid": "", "title": "Bad", "panels": []}), encoding="utf-8")

    result = runner.invoke(grafana_app, ["dashboards", "lint", str(bad), "--json"])

    assert (result.exit_code, json.loads(result.output)[0]["source_file"]) == (1, "bad.json")


def test_cli_supports_dry_run() -> None:
    """Linting runs normally under dry run as a no-external-request command."""
    result = runner.invoke(
        grafana_app,
        ["dashboards", "lint", str(_REPO_DASHBOARDS)],
        env={"DEVOPS_CLI_DRY_RUN": "true"},
    )
    assert result.exit_code == 0
    assert "Linted" in result.output


def test_sre_dashboards_contain_heatmap_and_ratio_panels() -> None:
    """Verify SRE dashboards include heatmap distributions and ratio-based saturation panels."""
    ingress_report = lint_dashboard_file(_REPO_DASHBOARDS / "ingress-tunnel.json")
    sre_report = lint_dashboard_file(_REPO_DASHBOARDS / "sre-service.json")

    ingress_dash = json.loads(
        (_REPO_DASHBOARDS / "ingress-tunnel.json").read_text(encoding="utf-8")
    )
    sre_dash = json.loads((_REPO_DASHBOARDS / "sre-service.json").read_text(encoding="utf-8"))

    ingress_heatmaps = [p["title"] for p in ingress_dash["panels"] if p.get("type") == "heatmap"]
    sre_heatmaps = [p["title"] for p in sre_dash["panels"] if p.get("type") == "heatmap"]

    ingress_ratios = [
        p["title"]
        for p in ingress_dash["panels"]
        if p.get("fieldConfig", {}).get("defaults", {}).get("unit") == "percent"
    ]
    sre_ratios = [
        p["title"]
        for p in sre_dash["panels"]
        if p.get("fieldConfig", {}).get("defaults", {}).get("unit") == "percent"
    ]

    assert (
        (len(ingress_report.errors), len(ingress_report.warnings)),
        (len(sre_report.errors), len(sre_report.warnings)),
        ingress_heatmaps,
        sre_heatmaps,
        ingress_ratios,
        sre_ratios,
    ) == (
        (0, 0),
        (0, 0),
        ["Ingress Request Latency Distribution (Heatmap)"],
        ["Service Request Duration Distribution (Heatmap)"],
        [
            "Cloudflare Tunnel Request Error Ratio (%)",
            "Ingress Success Rate",
            "Ingress Error Rate",
            "Ingress HTTP Status Code Ratios (Success vs. Error %)",
        ],
        [
            "Container Resource Saturation Ratios (% of Limit)",
            "CPU Throttling & Network Packet Drop Ratios (%)",
        ],
    )


def _assert_sre_service_dashboard_structure(sre_dash: dict[str, Any]) -> None:
    panels = sre_dash.get("panels", [])
    panel_map = {p["id"]: p for p in panels if "id" in p}
    row_11 = panel_map[11]
    top_logs = panel_map[21]
    lower_logs = panel_map[12]
    row_18 = panel_map[18]
    flamegraph_19 = panel_map[19]
    flamegraph_20 = panel_map[20]

    ordered_ids = [p["id"] for p in panels if p.get("id") in (11, 21, 12, 18)]
    assert ordered_ids == [11, 21, 12, 18]

    assert (
        (row_11["id"], row_11["type"], row_11["title"], row_11["gridPos"]),
        (top_logs["id"], top_logs["type"], top_logs["title"], top_logs["gridPos"]),
        (lower_logs["id"], lower_logs["type"], lower_logs["title"], lower_logs["gridPos"]),
        (row_18["id"], row_18["type"], row_18["title"], row_18["gridPos"]),
    ) == (
        (11, "row", "Service Logs & Live Stream", {"h": 1, "w": 24, "x": 0, "y": 38}),
        (21, "logs", "Warnings & Errors (Loki)", {"h": 8, "w": 24, "x": 0, "y": 39}),
        (12, "logs", "Live Service Logs (Loki)", {"h": 12, "w": 24, "x": 0, "y": 47}),
        (
            18,
            "row",
            "Continuous Profiling & Flamegraphs (Pyroscope)",
            {"h": 1, "w": 24, "x": 0, "y": 59},
        ),
    )

    top_target = top_logs["targets"][0]
    lower_target = lower_logs["targets"][0]
    top_expr = top_target["expr"]
    lower_expr = lower_target["expr"]

    assert (
        top_target["datasource"]["uid"],
        lower_target["datasource"]["uid"],
        top_expr,
        lower_expr,
    ) == (
        "loki",
        "loki",
        '{namespace=~"$namespace"} | pod=~"$pod" | detected_level=~"(?i)(warn|warning|error|err|critical|fatal|panic)"',
        '{namespace=~"$namespace"} | pod=~"$pod"',
    )

    level_filter = '| detected_level=~"(?i)(warn|warning|error|err|critical|fatal|panic)"'
    assert top_expr == f"{lower_expr} {level_filter}"
    assert "(?i)" in top_expr
    assert 'pod=~"$pod"' not in top_expr.split("|")[0]
    assert 'pod=~"$pod"' not in lower_expr.split("|")[0]

    assert (flamegraph_19["gridPos"], flamegraph_20["gridPos"]) == (
        {"h": 12, "w": 24, "x": 0, "y": 60},
        {"h": 12, "w": 24, "x": 0, "y": 72},
    )

    assert top_logs["options"] == lower_logs["options"]

    top_desc = top_logs.get("description", "")
    assert "namespace" in top_desc
    assert "pods" in top_desc
    assert "Kubernetes Warning events" in top_desc

    lower_desc = lower_logs.get("description", "")
    assert "namespace" in lower_desc
    assert "pods" in lower_desc
    assert "service" not in lower_desc.lower()


def test_sre_service_dashboard_structure() -> None:
    """Verify sre-service.json row 11 log panels, row 18, and flamegraphs structure."""
    sre_dash = json.loads((_REPO_DASHBOARDS / "sre-service.json").read_text(encoding="utf-8"))
    _assert_sre_service_dashboard_structure(sre_dash)


def test_sre_service_dashboard_structure_mutations() -> None:
    """Verify that each required mutation causes _assert_sre_service_dashboard_structure to fail."""
    import copy

    sre_dash = json.loads((_REPO_DASHBOARDS / "sre-service.json").read_text(encoding="utf-8"))

    # Mutation 1: putting pod=~"$pod" back inside the stream selector
    m1 = copy.deepcopy(sre_dash)
    for p in m1["panels"]:
        if p.get("id") == 12:
            p["targets"][0]["expr"] = '{namespace=~"$namespace", pod=~"$pod"}'
    with pytest.raises(AssertionError, match=r'pod=~"\$pod"'):
        _assert_sre_service_dashboard_structure(m1)

    # Mutation 2: dropping (?i)
    m2 = copy.deepcopy(sre_dash)
    for p in m2["panels"]:
        if p.get("id") == 21:
            p["targets"][0]["expr"] = (
                '{namespace=~"$namespace"} | pod=~"$pod" | detected_level=~"(warn|warning|error|err|critical|fatal|panic)"'
            )
    with pytest.raises(AssertionError, match=r"\(\?i\)"):
        _assert_sre_service_dashboard_structure(m2)

    # Mutation 3: swapping the two log panels' y
    m3 = copy.deepcopy(sre_dash)
    for p in m3["panels"]:
        if p.get("id") == 21:
            p["gridPos"]["y"] = 47
        elif p.get("id") == 12:
            p["gridPos"]["y"] = 39
    with pytest.raises(AssertionError, match=r"'y': 47"):
        _assert_sre_service_dashboard_structure(m3)

    # Mutation 4: leaving row 18 at y=51
    m4 = copy.deepcopy(sre_dash)
    for p in m4["panels"]:
        if p.get("id") == 18:
            p["gridPos"]["y"] = 51
    with pytest.raises(AssertionError, match=r"'y': 51"):
        _assert_sre_service_dashboard_structure(m4)


def test_sre_service_dashboard_readme_entry() -> None:
    """k8s/README.md gives the dashboard its real title and lists both log panels."""
    readme = (REPO_ROOT / "k8s" / "README.md").read_text(encoding="utf-8")
    entry = next(
        line
        for line in readme.splitlines()
        if "sre-service.json" in line and "devops-sre-service" in line
    )
    assert "SRE / Service Performance & Logs" in entry
    assert "Warnings & Errors (Loki)" in entry
    assert "Live Service Logs (Loki)" in entry


def test_dashboards_contain_properly_labeled_sum_and_average_lines() -> None:
    """Verify service, ingress and k8s dashboards contain properly labeled sum/avg queries."""
    in_scope_panels = [
        ("sre-service.json", 7, "CPU Usage by Pod", True),
        ("sre-service.json", 8, "Memory Working Set by Pod", True),
        ("ingress-tunnel.json", 16, "Service Request Rate", True),
        ("ingress-tunnel.json", 21, "Ingress & Tunnel Pod CPU Usage", True),
        ("ingress-tunnel.json", 22, "Ingress & Tunnel Memory Working Set", True),
        ("k8s-views-nodes.json", 26, "CPU usage by Pod", True),
        ("k8s-views-nodes.json", 28, "Memory usage by Pod", True),
        ("k8s-views-pods.json", 29, "CPU Usage by container", True),
        ("k8s-views-pods.json", 51, "Memory Usage by container", True),
    ]

    dashboards = {
        dash_name: json.loads((_REPO_DASHBOARDS / dash_name).read_text(encoding="utf-8"))
        for dash_name in {entry[0] for entry in in_scope_panels}
    }

    for dash_name, panel_id, panel_title, has_total in in_scope_panels:
        dash = dashboards[dash_name]
        panel = next((p for p in dash.get("panels", []) if p.get("id") == panel_id), None)
        assert panel is not None, f"Panel id {panel_id} not found in {dash_name}"
        assert panel.get("title") == panel_title, (
            f"Panel id {panel_id} title mismatch in {dash_name}"
        )

        targets = panel.get("targets", [])
        ref_a = next((t for t in targets if t.get("refId") == "A"), None)
        assert ref_a is not None, f"RefId A missing in {dash_name} panel {panel_id}"
        ref_a_expr = ref_a.get("expr", "")
        assert ref_a_expr, f"RefId A expr empty in {dash_name} panel {panel_id}"

        overrides = panel.get("fieldConfig", {}).get("overrides", [])

        if has_total:
            total_target = next(
                (t for t in targets if t.get("legendFormat") == "Total (Sum)"), None
            )
            assert total_target is not None, (
                f"Total (Sum) target missing in {dash_name} panel {panel_id}"
            )
            assert total_target.get("expr") == f"sum({ref_a_expr})", (
                f"Total (Sum) expr mismatch in {dash_name} panel {panel_id}: "
                f"{total_target.get('expr')!r} != {f'sum({ref_a_expr})'!r}"
            )

            total_override = next(
                (
                    ov
                    for ov in overrides
                    if ov.get("matcher", {}).get("id") == "byName"
                    and ov.get("matcher", {}).get("options") == "Total (Sum)"
                ),
                None,
            )
            assert total_override is not None, (
                f"Total (Sum) override missing in {dash_name} panel {panel_id}"
            )
            total_props = {
                p.get("id"): p.get("value") for p in total_override.get("properties", [])
            }
            line_style = total_props.get("custom.lineStyle")
            assert isinstance(line_style, dict)
            assert line_style.get("fill") == "dash", (
                f"Total (Sum) lineStyle.fill must be 'dash' in {dash_name} panel {panel_id}"
            )
            assert total_props.get("custom.lineWidth") == 2, (
                f"Total (Sum) lineWidth must be 2 in {dash_name} panel {panel_id}"
            )
            color = total_props.get("color")
            assert isinstance(color, dict)
            assert color.get("mode") == "fixed", (
                f"Total (Sum) color.mode must be 'fixed' in {dash_name} panel {panel_id}"
            )
            assert "custom.axisPlacement" not in total_props, (
                f"Total (Sum) must not override custom.axisPlacement in {dash_name} panel {panel_id}"
            )
        else:
            assert not any(t.get("legendFormat") == "Total (Sum)" for t in targets), (
                f"Total (Sum) target must not exist in {dash_name} panel {panel_id}"
            )

        avg_target = next((t for t in targets if t.get("legendFormat") == "Average (Mean)"), None)
        assert avg_target is not None, (
            f"Average (Mean) target missing in {dash_name} panel {panel_id}"
        )
        assert avg_target.get("expr") == f"avg({ref_a_expr})", (
            f"Average (Mean) expr mismatch in {dash_name} panel {panel_id}: "
            f"{avg_target.get('expr')!r} != {f'avg({ref_a_expr})'!r}"
        )

        avg_override = next(
            (
                ov
                for ov in overrides
                if ov.get("matcher", {}).get("id") == "byName"
                and ov.get("matcher", {}).get("options") == "Average (Mean)"
            ),
            None,
        )
        assert avg_override is not None, (
            f"Average (Mean) override missing in {dash_name} panel {panel_id}"
        )
        avg_props = {p.get("id"): p.get("value") for p in avg_override.get("properties", [])}
        line_style = avg_props.get("custom.lineStyle")
        assert isinstance(line_style, dict)
        assert line_style.get("fill") == "dash", (
            f"Average (Mean) lineStyle.fill must be 'dash' in {dash_name} panel {panel_id}"
        )
        assert avg_props.get("custom.lineWidth") == 2, (
            f"Average (Mean) lineWidth must be 2 in {dash_name} panel {panel_id}"
        )
        color = avg_props.get("color")
        assert isinstance(color, dict)
        assert color.get("mode") == "fixed", (
            f"Average (Mean) color.mode must be 'fixed' in {dash_name} panel {panel_id}"
        )
        assert "custom.axisPlacement" not in avg_props, (
            f"Average (Mean) must not override custom.axisPlacement in {dash_name} panel {panel_id}"
        )


def test_enhanced_dashboard_panels_and_visualizations() -> None:
    """Verify newly enhanced panels in SRE, AI spend, LLM, Ingress, and DevOps CLI dashboards."""
    sre_dash = json.loads((_REPO_DASHBOARDS / "sre-service.json").read_text(encoding="utf-8"))
    ai_dash = json.loads((_REPO_DASHBOARDS / "ai-spend.json").read_text(encoding="utf-8"))
    llm_dash = json.loads((_REPO_DASHBOARDS / "llm-stack.json").read_text(encoding="utf-8"))
    ingress_dash = json.loads(
        (_REPO_DASHBOARDS / "ingress-tunnel.json").read_text(encoding="utf-8")
    )
    cli_dash = json.loads((_REPO_DASHBOARDS / "devops-cli.json").read_text(encoding="utf-8"))

    sre_flamegraphs = [
        (p["title"], p["gridPos"]["w"]) for p in sre_dash["panels"] if p.get("type") == "flamegraph"
    ]
    ai_projections = [p["title"] for p in ai_dash["panels"] if "Projected" in p.get("title", "")]
    savings_panel = next(
        p for p in ai_dash["panels"] if p.get("title") == "Local Savings per Hour by Backend Server"
    )
    custom_savings = savings_panel.get("fieldConfig", {}).get("defaults", {}).get("custom", {})
    gpu_mem_panel = next(
        p for p in llm_dash["panels"] if p.get("title") == "GPU Memory Utilization (%)"
    )
    gpu_custom = gpu_mem_panel.get("fieldConfig", {}).get("defaults", {}).get("custom", {})
    ingress_router_panel = any(
        p.get("title") == "Traffic by Ingress Host / Router" for p in ingress_dash["panels"]
    )
    cli_command_var = any(
        v.get("name") == "command" for v in cli_dash.get("templating", {}).get("list", [])
    )

    assert (
        sre_flamegraphs,
        ai_projections,
        (custom_savings.get("drawStyle"), custom_savings.get("fillOpacity")),
        (gpu_custom.get("thresholdsStyle", {}).get("mode"), gpu_custom.get("axisSoftMax")),
        ingress_router_panel,
        cli_command_var,
    ) == (
        [
            ("CPU Profiling Flamegraph (process_cpu)", 24),
            ("Memory Profiling Flamegraph (inuse_space)", 24),
        ],
        [
            "Projected 30-Day Run Rate",
            "Projected 90-Day Run Rate",
            "Projected 1-Year Run Rate",
        ],
        ("line", 20),
        ("line", 100),
        True,
        True,
    )


def test_grafana_dashboard_projections_and_dcgm_grid_layout() -> None:
    """Verify aggregated rolling averages, dynamic projections, TTFT, and DCGM 2x2 grid."""
    ai_dash = json.loads((_REPO_DASHBOARDS / "ai-spend.json").read_text(encoding="utf-8"))
    llm_dash = json.loads((_REPO_DASHBOARDS / "llm-stack.json").read_text(encoding="utf-8"))
    dcgm_dash = json.loads((_REPO_DASHBOARDS / "nvidia-dcgm.json").read_text(encoding="utf-8"))
    proj_dash = json.loads((_REPO_DASHBOARDS / "project-metrics.json").read_text(encoding="utf-8"))

    ai_panels = {p["id"]: p for p in ai_dash.get("panels", [])}
    dcgm_panels = {p["id"]: p for p in dcgm_dash.get("panels", [])}
    llm_panels = {p["id"]: p for p in llm_dash.get("panels", [])}

    ai_roll_legends = [ai_panels[pid]["targets"][1]["legendFormat"] for pid in (8, 15, 10, 11)]
    ai_proj_ranges = [
        all("[$__range]" in t["expr"] for t in ai_panels[pid]["targets"]) for pid in (16, 17, 18)
    ]
    ttft_panel = llm_panels[8]
    dcgm_coords = [
        (
            dcgm_panels[pid]["gridPos"]["x"],
            dcgm_panels[pid]["gridPos"]["y"],
            dcgm_panels[pid]["gridPos"]["w"],
        )
        for pid in (2, 6, 4, 18)
    ]
    proj_has_increase = any(
        "increase(" in t.get("expr", "")
        for p in proj_dash.get("panels", [])
        for t in p.get("targets", [])
    )

    assert (
        ai_roll_legends,
        ai_proj_ranges,
        ttft_panel["title"],
        "sum by (le, model)" in ttft_panel["targets"][0]["expr"],
        dcgm_coords,
        proj_has_increase,
    ) == (
        [
            "Total Rolling Avg (6h)",
            "Total Rolling Avg (6h)",
            "Total Rolling Avg (30m)",
            "Total Rolling Avg (30m)",
        ],
        [True, True, True],
        "Time to First Token p95 per Model",
        True,
        [(0, 16, 12), (12, 16, 12), (0, 24, 12), (12, 24, 12)],
        False,
    )


def _llm_stack_panels() -> dict[int, dict[str, Any]]:
    """The panels of `llm-stack.json` by id."""
    llm_dash = json.loads((_REPO_DASHBOARDS / "llm-stack.json").read_text(encoding="utf-8"))
    return {panel["id"]: panel for panel in llm_dash["panels"]}


def test_llm_stack_time_series_take_each_rate_over_the_rate_interval() -> None:
    """A time series of `llm-stack.json` holds no fixed range window, so a short peak stays
    visible at a wide time range (#4732)."""
    fixed_windows = sorted(
        (panel["title"], target["refId"], window)
        for panel in _llm_stack_panels().values()
        if panel.get("type") == "timeseries"
        for target in panel.get("targets", [])
        for window in re.findall(r"\[[^\]]*\]", target["expr"])
        if window != "[$__rate_interval]"
    )

    assert fixed_windows == []


def test_llm_stack_breakdown_panels_add_a_total_only_to_requests_and_power() -> None:
    """A breakdown panel of `llm-stack.json` draws one line per entity and no mean or rolling
    line; only calls, requests and power add `Total (Sum)`. GPU memory is in MiB (#4732)."""
    panels = _llm_stack_panels()
    gpu = "{{hostname}} GPU {{gpu}} ({{modelName}})"

    assert {
        panel_id: (
            panels[panel_id]["title"],
            panels[panel_id]["fieldConfig"]["defaults"]["unit"],
            [(target["refId"], target["legendFormat"]) for target in panels[panel_id]["targets"]],
            [
                override["matcher"]["options"]
                for override in panels[panel_id]["fieldConfig"].get("overrides", [])
            ],
            [
                target["expr"] == f"sum({panels[panel_id]['targets'][0]['expr']})"
                for target in panels[panel_id]["targets"][1:]
            ],
        )
        for panel_id in (2, 4, 13, 14, 15, 17)
    } == {
        2: (
            "Calls in Flight per Deployment",
            "short",
            [("A", "{{api_base}}"), ("B", "Total (Sum)")],
            ["Total (Sum)"],
            [True],
        ),
        4: (
            "Requests per Deployment",
            "reqps",
            [("A", "{{api_base}}"), ("B", "Total (Sum)")],
            ["Total (Sum)"],
            [True],
        ),
        13: ("GPU Utilisation", "percent", [("A", gpu)], [], []),
        14: ("GPU Memory Used", "mbytes", [("A", gpu)], [], []),
        15: ("GPU Power", "watt", [("A", gpu), ("B", "Total (Sum)")], ["Total (Sum)"], [True]),
        17: ("GPU Memory Utilization (%)", "percent", [("A", gpu)], [], []),
    }


def test_llm_stack_counts_only_the_model_routes() -> None:
    """The virtual model and status code panels of `llm-stack.json` count only the chat and
    embeddings routes, as `ai-spend.json` does, not a gateway route such as `/v1/systemone`
    (#4732)."""
    panels = _llm_stack_panels()

    assert [panels[panel_id]["targets"][0]["expr"] for panel_id in (21, 22)] == [
        "sum by (requested_model) (rate(litellm_proxy_total_requests_metric_total"
        '{route=~"/v1/(chat/completions|embeddings)"}[$__rate_interval]))',
        "sum by (status_code) (rate(litellm_proxy_total_requests_metric_total"
        '{route=~"/v1/(chat/completions|embeddings)"}[$__rate_interval]))',
    ]


def test_llm_stack_counts_cooldowns_and_fallbacks_in_the_time_range() -> None:
    """Cooldowns and fallbacks of `llm-stack.json` are stats of the count in the time range, and
    show "none recorded" with no series rather than a constant zero (#4732)."""
    panels = _llm_stack_panels()

    assert {
        panel_id: (
            panels[panel_id]["type"],
            panels[panel_id]["title"],
            panels[panel_id]["fieldConfig"]["defaults"].get("noValue"),
            [
                (target["refId"], target["expr"], target.get("instant"))
                for target in panels[panel_id]["targets"]
            ],
        )
        for panel_id in (24, 25)
    } == {
        24: (
            "stat",
            "Cooldowns per Deployment in Range",
            "none recorded",
            [
                (
                    "A",
                    "sum by (api_base, exception_status) "
                    "(increase(litellm_deployment_cooled_down_total[$__range]))",
                    True,
                )
            ],
        ),
        25: (
            "stat",
            "Fallbacks per Model Pair in Range",
            "none recorded",
            [
                (
                    "A",
                    "sum by (requested_model, fallback_model) "
                    "(increase(litellm_deployment_successful_fallbacks_total[$__range]))",
                    True,
                ),
                (
                    "B",
                    "sum by (requested_model, fallback_model) "
                    "(increase(litellm_deployment_failed_fallbacks_total[$__range]))",
                    True,
                ),
            ],
        ),
    }


def test_llm_stack_qdrant_row_draws_each_value_once_on_its_own_scale() -> None:
    """The Qdrant row of `llm-stack.json` draws each status once, shows the collection count as
    a stat and the vectors of each collection as lines (#4732)."""
    panels = _llm_stack_panels()

    assert [
        (panel["type"], panel["title"], [target["expr"] for target in panel["targets"]])
        for panel in panels.values()
        if panel["id"] in (27, 29, 34)
    ] == [
        (
            "timeseries",
            "Qdrant Request Rate and Errors",
            ["sum by (method, endpoint, status) (rate(rest_responses_total[$__rate_interval]))"],
        ),
        ("stat", "Qdrant Collections", ["sum(collections_total)"]),
        (
            "timeseries",
            "Qdrant Vectors per Collection",
            ["sum by (collection) (collection_vectors)"],
        ),
    ]


def test_cli_dashboard_finds_each_command_and_sub_command_from_its_series() -> None:
    """The `command` and `sub_command` variables of devops-cli.json read their values from the
    series that devops-cli sends, so a new command or sub-command shows with no change to the
    dashboard. `sub_command` holds only the sub-commands of the commands selected (#2700)."""
    cli_dash = json.loads((_REPO_DASHBOARDS / "devops-cli.json").read_text(encoding="utf-8"))
    variables = {v["name"]: v for v in cli_dash.get("templating", {}).get("list", [])}

    assert [
        (
            name,
            variables[name].get("type"),
            variables[name].get("definition"),
            variables[name].get("query", {}).get("query"),
            variables[name].get("datasource", {}).get("uid"),
            variables[name].get("multi"),
            variables[name].get("includeAll"),
            variables[name].get("allValue"),
            variables[name].get("refresh"),
            "options" in variables[name] and variables[name]["options"] != [],
        )
        for name in ("command", "sub_command")
    ] == [
        (
            "command",
            "query",
            'label_values(devops_cli_command_total{job=~"$job"}, command)',
            'label_values(devops_cli_command_total{job=~"$job"}, command)',
            "prometheus",
            True,
            True,
            ".*",
            2,
            False,
        ),
        (
            "sub_command",
            "query",
            'label_values(devops_cli_subcommand_duration_seconds{job=~"$job",command=~"$command"}, sub_command)',
            'label_values(devops_cli_subcommand_duration_seconds{job=~"$job",command=~"$command"}, sub_command)',
            "prometheus",
            True,
            True,
            ".*",
            2,
            False,
        ),
    ]


def _cli_dashboard_prometheus_queries() -> list[str]:
    """Each Prometheus query of the panels of devops-cli.json."""
    cli_dash = json.loads((_REPO_DASHBOARDS / "devops-cli.json").read_text(encoding="utf-8"))
    return [
        target["expr"]
        for panel in cli_dash["panels"]
        if panel.get("datasource", {}).get("type") != "loki"
        for target in panel.get("targets", [])
    ]


def test_cli_dashboard_finds_each_job_from_its_series() -> None:
    """The first variable of devops-cli.json is `job`, because a variable reads only the variables
    before it. The list follows the time range, and the Service adds to the command series only
    when it exits, so the variable also reads the GitHub requests that it sends as it works (#2479).
    """
    cli_dash = json.loads((_REPO_DASHBOARDS / "devops-cli.json").read_text(encoding="utf-8"))
    first = cli_dash["templating"]["list"][0]

    assert (
        first["name"],
        first["label"],
        first["type"],
        first["definition"],
        first["query"]["query"],
        first["datasource"]["uid"],
        first["multi"],
        first["includeAll"],
        first["allValue"],
        first["refresh"],
        first["options"],
    ) == (
        "job",
        "Job",
        "query",
        _JOB_VALUES,
        _JOB_VALUES,
        "prometheus",
        True,
        True,
        ".*",
        2,
        [],
    )


def test_each_prometheus_query_of_the_cli_dashboard_filters_by_job() -> None:
    """Each `devops_cli_*` series of each Prometheus query starts its selector with the `job`
    matcher, so a panel never adds the requests of a job that the reader did not select (#2479)."""
    queries = _cli_dashboard_prometheus_queries()
    unfiltered = [query for query in queries if _SERIES_WITH_NO_JOB_MATCHER.search(query)]

    assert (len(queries) > 0, unfiltered) == (True, [])


def _cli_dashboard_row(title: str) -> list[dict[str, Any]]:
    """The panels of the row `title` of devops-cli.json, in the order of the file."""
    cli_dash = json.loads((_REPO_DASHBOARDS / "devops-cli.json").read_text(encoding="utf-8"))
    panels: list[dict[str, Any]] = cli_dash["panels"]
    start = next(i for i, p in enumerate(panels) if p.get("type") == "row" and p["title"] == title)
    end = next(
        (i for i in range(start + 1, len(panels)) if panels[i].get("type") == "row"), len(panels)
    )
    return panels[start + 1 : end]


def test_cli_dashboard_service_row_charts_the_state_of_the_service() -> None:
    """The row "Roadmap Service" holds a panel for the rounds, the budget, the queues, the stops
    and the inputs of the Service (#2479), and for the failed deliveries of the hooks (#5017)."""
    selector = '{job=~"$job"}'

    assert {
        p["title"]: [t["expr"] for t in p["targets"]] for p in _cli_dashboard_row("Roadmap Service")
    } == {
        "Service Rounds by Lane and Result": [
            f"sum by (lane, result) (increase(devops_cli_service_jobs_total{selector}[1h]))"
        ],
        "Service Failed Rounds by Repository and Row": [
            "sum by (repo, row) (increase(devops_cli_service_jobs_total"
            '{job=~"$job",result="error"}[1h]))'
        ],
        "Service Round Seconds by Lane": [
            f"sum by (lane) (increase(devops_cli_service_job_seconds_total{selector}[1h]))"
        ],
        "Service GitHub Budget": [
            f"max(last_over_time(devops_cli_service_budget_spent_requests{selector}[5m]))",
            f"max(last_over_time(devops_cli_service_budget_limit_requests{selector}[5m]))",
        ],
        "Service Budget Holds": [
            f"sum(increase(devops_cli_service_budget_holds_total{selector}[1h])) or vector(0)"
        ],
        "Service Time Since Round Start": [
            "time() - max by (repo, lane) "
            f"(last_over_time(devops_cli_service_job_start_timestamp_seconds{selector}[5m]))"
        ],
        "Service Queue Depth by Lane": [
            f"sum by (lane) (last_over_time(devops_cli_service_queue_depth{selector}[5m]))"
        ],
        "Service Suspended Rows": [
            f"max by (repo, row) (last_over_time(devops_cli_service_job_suspended{selector}[5m]))"
        ],
        "Service Identity Refusals": [
            "max by (identity) "
            f"(last_over_time(devops_cli_service_identity_refused_total{selector}[5m]))"
        ],
        "Service Triggers by Source": [
            f"sum by (source) (increase(devops_cli_service_triggers_total{selector}[1h]))"
        ],
        "Service Webhook Deliveries by Outcome": [
            "sum by (outcome) "
            f"(increase(devops_cli_service_webhook_deliveries_total{selector}[1h]))"
        ],
        "Service Implement Failures by Class": [
            f"sum by (class) (increase(devops_cli_service_implement_failures_total{selector}[1h]))"
        ],
        "Service Chat Commands by Result": [
            "sum by (command, result) "
            f"(increase(devops_cli_service_chat_commands_total{selector}[1h]))"
        ],
        "Service Unkept State Records": [
            f"max by (record) (last_over_time(devops_cli_service_state_unkept{selector}[5m]))"
        ],
        "Service Retry After Seconds": [
            "max by (repo, row, class) "
            f"(last_over_time(devops_cli_service_job_retry_after_seconds{selector}[5m]))"
        ],
        "Service Failed Webhook Deliveries": [
            "max by (repo, code) "
            f"(last_over_time(devops_cli_service_webhook_delivery_failures{selector}[5m]))"
        ],
    }


def test_cli_dashboard_service_row_reads_each_series_of_the_service() -> None:
    """Each metric name that the Service declares has a query in the row, so a new series of the
    Service that the row does not chart fails here (#2479). The metrics of #3069 are charted by
    #3655."""
    deferred_metrics = {
        constants.CONST_SERVICE_METRIC_IMPLEMENT_JOBS,
        constants.CONST_SERVICE_METRIC_IMPLEMENT_REPAIR_ROUNDS,
        constants.CONST_SERVICE_METRIC_IMPLEMENT_TOKENS,
        constants.CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES,
    }
    declared = {
        value
        for name, value in vars(constants).items()
        if name.startswith("CONST_SERVICE_METRIC_") and value not in deferred_metrics
    }
    queried = {
        name
        for panel in _cli_dashboard_row("Roadmap Service")
        for target in panel["targets"]
        for name in re.findall(r"devops_cli_service_[a-z0-9_]+", target["expr"])
    }

    assert queried == declared


def test_cli_dashboard_panels_do_not_overlap() -> None:
    """The panels fill a grid of 24 columns, and no two panels hold the same cell, so the row
    "Roadmap Service" keeps its place below the row before it (#2479)."""
    cli_dash = json.loads((_REPO_DASHBOARDS / "devops-cli.json").read_text(encoding="utf-8"))
    cells: list[tuple[int, int]] = []
    for panel in cli_dash["panels"]:
        grid = panel["gridPos"]
        cells.extend(
            (grid["x"] + x, grid["y"] + y) for x in range(grid["w"]) for y in range(grid["h"])
        )
    ids = [panel["id"] for panel in cli_dash["panels"]]

    assert (
        len(cells) == len(set(cells)),
        max(x for x, _ in cells) < 24,
        len(ids) == len(set(ids)),
    ) == (True, True, True)


def test_cli_dashboard_shows_the_selected_sub_commands_in_one_table() -> None:
    """The sub-command row has one table of the calls, errors and latency of each selected
    `sub_command` in the range, filtered by `$job`, `$command` and `$sub_command`. No panel
    repeats for each sub-command (#2700, #4707)."""
    row = _cli_dashboard_row("Sub-commands")
    selector = (
        'devops_cli_subcommand_duration_seconds{job=~"$job",command=~"$command",'
        'sub_command=~"$sub_command"'
    )

    assert [
        (
            p["title"],
            p["type"],
            p.get("repeat"),
            all(selector in t["expr"] and t.get("instant") for t in p["targets"]),
        )
        for p in row
    ] == [("Sub-commands: calls, errors and latency in the range", "table", None, True)]


def test_profiling_dashboards_query_pyroscope_service_name_without_created_by_name() -> None:
    """Neither profiling dashboard hard-codes a `service_name` list or reads `created_by_name` (#1134)."""
    pyro_raw = (_REPO_DASHBOARDS / "pyroscope.json").read_text(encoding="utf-8")
    sre_raw = (_REPO_DASHBOARDS / "sre-service.json").read_text(encoding="utf-8")
    pyro_dash = json.loads(pyro_raw)
    sre_dash = json.loads(sre_raw)

    pyro_service = next(v for v in pyro_dash["templating"]["list"] if v["name"] == "service")
    sre_service = next(v for v in sre_dash["templating"]["list"] if v["name"] == "service")
    sre_flamegraphs = [
        (t["expr"], t["labelSelector"])
        for p in sre_dash["panels"]
        if p.get("type") == "flamegraph"
        for t in p.get("targets", [])
    ]

    assert (
        (
            pyro_service["type"],
            pyro_service["datasource"]["uid"],
            pyro_service["query"],
            pyro_service.get("options", []),
        ),
        (
            sre_service["type"],
            sre_service["datasource"]["uid"],
            sre_service["query"],
            sre_service.get("options", []),
        ),
        sre_flamegraphs,
        "monitoring/pyroscope" in pyro_raw or "monitoring/alloy" in pyro_raw,
        "created_by_name" in pyro_raw or "created_by_name" in sre_raw,
    ) == (
        ("query", "pyroscope", "label_values(service_name)", []),
        ("query", "pyroscope", 'label_values({service_namespace="$namespace"}, service_name)', []),
        [
            (
                'process_cpu:cpu:nanoseconds:cpu:nanoseconds{service_namespace="$namespace", service_name=~"$service"}',
                '{service_namespace="$namespace", service_name=~"$service"}',
            ),
            (
                'memory:inuse_space:bytes:space:bytes{service_namespace="$namespace", service_name=~"$service"}',
                '{service_namespace="$namespace", service_name=~"$service"}',
            ),
        ],
        False,
        False,
    )


def test_loki_datasource_derived_field_links_to_tempo() -> None:
    """Verify Loki datasource in grafana-values.yaml defines derivedFields pointing to Tempo (#813)."""
    values_path = REPO_ROOT / "k8s" / "monitoring" / "grafana-values.yaml"
    values = yaml.safe_load(values_path.read_text(encoding="utf-8"))
    datasources = values["datasources"]["datasources.yaml"]["datasources"]
    loki_ds = next(ds for ds in datasources if ds["name"] == "Loki")
    derived_fields = loki_ds.get("jsonData", {}).get("derivedFields", [])
    assert len(derived_fields) >= 1
    tempo_field = next(df for df in derived_fields if df.get("datasourceUid") == "tempo")
    assert tempo_field["name"] == "TraceID"
    assert "trace_id" in tempo_field["matcherRegex"]
    assert tempo_field["url"] == "$${__value.raw}"


def test_devops_cli_dashboard_includes_error_stream_panel() -> None:
    """Verify devops-cli dashboard includes a Loki logs panel of the error records only: the
    levels error, critical and fatal, and no warnings (#813, #4707)."""
    cli_dash = json.loads((_REPO_DASHBOARDS / "devops-cli.json").read_text(encoding="utf-8"))
    (error_panel,) = [p for p in cli_dash["panels"] if p.get("type") == "logs"]

    assert (
        error_panel["title"],
        error_panel["datasource"]["uid"],
        [t["expr"] for t in error_panel["targets"]],
    ) == (
        "Errors: error logs of devops-cli",
        "loki",
        ['{service_name="devops-cli"} | detected_level=~"error|critical|fatal"'],
    )
