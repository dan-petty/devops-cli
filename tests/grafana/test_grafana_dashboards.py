"""Unit tests for declarative Grafana dashboard schema, builders, and linting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.grafana import app as grafana_app
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


def test_dashboards_contain_properly_labeled_sum_and_average_lines() -> None:
    """Verify service, ingress, k8s, and LLM dashboards contain properly labeled sum/avg queries."""
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
        ("llm-stack.json", 2, "Calls in Flight per Deployment", True),
        ("llm-stack.json", 4, "Requests per Deployment", True),
        ("llm-stack.json", 13, "GPU Utilisation", False),
        ("llm-stack.json", 14, "GPU Memory Used", True),
        ("llm-stack.json", 15, "GPU Power", True),
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
    cli_repeat_panel = any(p.get("repeat") == "sub_command" for p in cli_dash.get("panels", []))

    assert (
        sre_flamegraphs,
        ai_projections,
        (custom_savings.get("drawStyle"), custom_savings.get("fillOpacity")),
        (gpu_custom.get("thresholdsStyle", {}).get("mode"), gpu_custom.get("axisSoftMax")),
        ingress_router_panel,
        cli_command_var,
        cli_repeat_panel,
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
            "label_values(devops_cli_command_total, command)",
            "label_values(devops_cli_command_total, command)",
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
            'label_values(devops_cli_subcommand_duration_seconds{command=~"$command"}, sub_command)',
            'label_values(devops_cli_subcommand_duration_seconds{command=~"$command"}, sub_command)',
            "prometheus",
            True,
            True,
            ".*",
            2,
            False,
        ),
    ]


def test_cli_dashboard_repeats_a_latency_panel_for_each_selected_sub_command() -> None:
    """The sub-command row has one calls panel by `sub_command` and one latency panel that
    repeats for each selected `sub_command`, titled with it and filtered to it (#2700)."""
    cli_dash = json.loads((_REPO_DASHBOARDS / "devops-cli.json").read_text(encoding="utf-8"))
    panels = cli_dash["panels"]
    start = next(
        i for i, p in enumerate(panels) if p.get("type") == "row" and p["title"] == "Sub-commands"
    )
    end = next(
        (i for i in range(start + 1, len(panels)) if panels[i].get("type") == "row"), len(panels)
    )
    row = panels[start + 1 : end]
    selector = (
        'devops_cli_subcommand_duration_seconds{command=~"$command",sub_command=~"$sub_command"'
    )

    assert [
        (
            p["title"],
            p.get("repeat"),
            p.get("repeatDirection"),
            p.get("maxPerRow"),
            all(selector in t["expr"] for t in p["targets"]),
        )
        for p in row
    ] == [
        ("Sub-command Calls", None, None, None, True),
        ("Telemetry: $sub_command", "sub_command", "h", 4, True),
    ]


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
    """Verify devops-cli dashboard includes a Loki error stream logs panel (#813)."""
    cli_dash = json.loads((_REPO_DASHBOARDS / "devops-cli.json").read_text(encoding="utf-8"))
    log_panels = [p for p in cli_dash["panels"] if p.get("type") == "logs"]
    assert len(log_panels) >= 1
    error_panel = next(p for p in log_panels if p.get("title") == "devops-cli Error Stream")
    assert error_panel["datasource"]["uid"] == "loki"
    targets = error_panel["targets"]
    assert len(targets) >= 1
    assert '{service_name="devops-cli"}' in targets[0]["expr"]
