"""Unit tests for declarative Grafana dashboard schema, builders, and linting."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.grafana import app as grafana_app
from devops_cli.config import constants
from devops_cli.grafana import (
    lint_dashboard,
    lint_dashboard_file,
    lint_dashboard_files,
    load_dashboard,
)
from devops_cli.grafana.schema import Dashboard, Datasource, GridPos, Panel, Target
from tests.support.paths import REPO_ROOT

runner = CliRunner()

# The product dashboards of devops-cli (#5292).
_PRODUCT_DASHBOARDS = REPO_ROOT / "k8s" / "devops" / "dashboards"
_REPO_DASHBOARD_FILES = sorted(_PRODUCT_DASHBOARDS.glob("*.json"))


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


# ─────────────────────────────────────────────────────────────────────────────
# 3. Builders
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# 5. Linting: real dashboards must pass
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("dashboard_file", _REPO_DASHBOARD_FILES, ids=lambda p: p.name)
def test_repository_dashboards_lint_clean(dashboard_file: Path) -> None:
    """The dashboards actually shipped in this repository must lint without errors.

    These are hand-authored and known to render, so any error here is a false positive in
    the linter rather than a defect in the dashboard.
    """
    report = lint_dashboard_file(dashboard_file)
    assert report.errors == [], f"{dashboard_file.name}: {[i.message for i in report.errors]}"


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


def test_cli_lints_each_dashboard_of_each_folder_given(tmp_path: Path) -> None:
    """The lint command reports a clean run over the dashboards of both folders."""
    first, second = tmp_path / "first", tmp_path / "second"
    for folder, name in ((first, "a"), (second, "b")):
        folder.mkdir()
        _write_dashboards(folder, {f"{name}.json": name})

    result = runner.invoke(grafana_app, ["dashboards", "lint", str(first), str(second)])

    assert (result.exit_code, "0 error(s)" in result.output) == (0, True)


def test_cli_with_no_path_lints_the_environment_and_the_product_dashboards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no path, the lint command reads `monitoring/dashboards` of the environment tree and
    `dashboards` of the product base `k8s/devops` of the current repository, so a uid that two
    folders share is an error too (#5292, #5131)."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "project.toml").write_text('[kubernetes]\ndir = "k8s"\n', "utf-8")
    for folder, name in (("k8s/monitoring/dashboards", "a"), ("k8s/devops/dashboards", "b")):
        (tmp_path / folder).mkdir(parents=True)
        _write_dashboards(tmp_path / folder, {f"{name}.json": name})
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(grafana_app, ["dashboards", "lint", "--json"])

    assert (
        result.exit_code,
        sorted(report["source_file"] for report in json.loads(result.output)),
    ) == (0, ["a.json", "b.json"])


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


def test_cli_json_output_is_machine_readable(tmp_path: Path) -> None:
    """Reports serialise for downstream tooling."""
    _write_dashboards(tmp_path, {"a.json": "a", "b.json": "b"})

    result = runner.invoke(grafana_app, ["dashboards", "lint", str(tmp_path), "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert len(payload) == 2


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


def test_cli_supports_dry_run(tmp_path: Path) -> None:
    """Linting runs normally under dry run as a no-external-request command."""
    _write_dashboards(tmp_path, {"a.json": "a"})

    result = runner.invoke(
        grafana_app,
        ["dashboards", "lint", str(tmp_path)],
        env={"DEVOPS_CLI_DRY_RUN": "true"},
    )
    assert result.exit_code == 0
    assert "Linted" in result.output


def _cli_dashboard_row(title: str) -> list[dict[str, Any]]:
    """The panels of the row `title` across product dashboards, in the order of the file."""
    for dash_name in ("devops-cli.json", "roadmap-service-telemetry.json", "devops-ai-rag.json"):
        path = _PRODUCT_DASHBOARDS / dash_name
        if not path.is_file():
            continue
        cli_dash = json.loads(path.read_text(encoding="utf-8"))
        panels: list[dict[str, Any]] = cli_dash["panels"]
        try:
            start = next(
                i for i, p in enumerate(panels) if p.get("type") == "row" and p["title"] == title
            )
        except StopIteration:
            continue
        end = next(
            (i for i in range(start + 1, len(panels)) if panels[i].get("type") == "row"),
            len(panels),
        )
        return panels[start + 1 : end]
    raise ValueError(f"Row {title!r} not found in product dashboards")


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
