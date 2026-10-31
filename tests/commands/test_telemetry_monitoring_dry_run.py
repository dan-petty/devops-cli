"""Tests for dry-run request plans and classifications across 21 monitoring and telemetry commands.

Issue #2254: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.dashboard import main_dashboard
from devops_cli.commands.grafana import (
    alerts as grafana_alerts,
)
from devops_cli.commands.grafana import (
    dashboards_export as grafana_dashboards_export,
)
from devops_cli.commands.grafana import (
    dashboards_import as grafana_dashboards_import,
)
from devops_cli.commands.grafana import (
    dashboards_lint as grafana_dashboards_lint,
)
from devops_cli.commands.grafana import (
    dashboards_list as grafana_dashboards_list,
)
from devops_cli.commands.grafana import (
    dashboards_sync as grafana_dashboards_sync,
)
from devops_cli.commands.grafana import (
    datasources as grafana_datasources,
)
from devops_cli.commands.grafana import (
    search as grafana_search,
)
from devops_cli.commands.prometheus import (
    analyze as prometheus_analyze,
)
from devops_cli.commands.prometheus import (
    query as prometheus_query,
)
from devops_cli.commands.prometheus import (
    query_range as prometheus_query_range,
)
from devops_cli.commands.prometheus import (
    rules as prometheus_rules,
)
from devops_cli.commands.prometheus import (
    targets as prometheus_targets,
)
from devops_cli.commands.telemetry import (
    telemetry_connect_cmd,
    telemetry_logfire_cmd,
    telemetry_open_ui_cmd,
    telemetry_profile_cmd,
    telemetry_semconv_refresh_cmd,
    telemetry_status_cmd,
    telemetry_test_cmd,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.grafana.grafana_plans import (
    plan_grafana_alerts,
    plan_grafana_dashboards_export,
    plan_grafana_dashboards_import,
    plan_grafana_dashboards_list,
    plan_grafana_dashboards_sync,
    plan_grafana_datasources,
    plan_grafana_search,
)
from devops_cli.main import app
from devops_cli.prometheus.prometheus_plans import (
    plan_prometheus_analyze,
    plan_prometheus_query,
    plan_prometheus_query_range,
    plan_prometheus_rules,
    plan_prometheus_targets,
)
from devops_cli.telemetry.telemetry_plans import (
    plan_dashboard,
    plan_telemetry_connect,
    plan_telemetry_profile,
    plan_telemetry_semconv_refresh,
    plan_telemetry_status,
    plan_telemetry_test,
)

runner = CliRunner()

COMMANDS_TO_CLASSIFY = [
    # Dashboard (1)
    (main_dashboard, "request-plan"),
    # Grafana (8)
    (grafana_alerts, "request-plan"),
    (grafana_dashboards_export, "request-plan"),
    (grafana_dashboards_import, "request-plan"),
    (grafana_dashboards_lint, "no-external-request"),
    (grafana_dashboards_list, "request-plan"),
    (grafana_dashboards_sync, "request-plan"),
    (grafana_datasources, "request-plan"),
    (grafana_search, "request-plan"),
    # Prometheus (5)
    (prometheus_analyze, "request-plan"),
    (prometheus_query, "request-plan"),
    (prometheus_query_range, "request-plan"),
    (prometheus_rules, "request-plan"),
    (prometheus_targets, "request-plan"),
    # Telemetry (7)
    (telemetry_connect_cmd, "request-plan"),
    (telemetry_logfire_cmd, "no-external-request"),
    (telemetry_open_ui_cmd, "no-external-request"),
    (telemetry_profile_cmd, "request-plan"),
    (telemetry_semconv_refresh_cmd, "request-plan"),
    (telemetry_status_cmd, "request-plan"),
    (telemetry_test_cmd, "request-plan"),
]

GAP_COMMAND_NAMES = [
    "dashboard",
    "grafana alerts",
    "grafana dashboards export",
    "grafana dashboards import",
    "grafana dashboards lint",
    "grafana dashboards list",
    "grafana dashboards sync",
    "grafana datasources",
    "grafana search",
    "prometheus analyze",
    "prometheus query",
    "prometheus query-range",
    "prometheus rules",
    "prometheus targets",
    "telemetry connect",
    "telemetry logfire",
    "telemetry open-ui",
    "telemetry profile",
    "telemetry semconv refresh",
    "telemetry status",
    "telemetry test",
    "tui",
]


@pytest.mark.parametrize("callback,expected_class", COMMANDS_TO_CLASSIFY)
def test_monitoring_telemetry_dry_run_classification(callback: Any, expected_class: str) -> None:
    """Verify each command callback has the expected dry-run classification."""
    actual_class = get_dry_run_class(callback)
    assert actual_class == expected_class, (
        f"{callback.__name__} expected {expected_class}, got {actual_class}"
    )


def test_monitoring_telemetry_removed_from_gaps() -> None:
    """Verify all 21 monitoring and telemetry commands are removed from dry_run_gaps.json."""
    gap_file = Path("tests/fixtures/dry_run_gaps.json")
    with gap_file.open("r", encoding="utf-8") as f:
        gaps = json.load(f)
    for cmd in GAP_COMMAND_NAMES:
        assert cmd not in gaps, f"Command {cmd} should be removed from dry_run_gaps.json"


def test_dashboard_plan() -> None:
    """Test dashboard plan generator."""
    plans = plan_dashboard()
    assert len(plans) >= 4
    methods = [p.method for p in plans]
    assert "kubectl" in methods or "GET" in methods
    assert "docker" in methods or "GET" in methods
    assert "valkey" in methods


def test_grafana_plans() -> None:
    """Test Grafana plan builders."""
    base = "https://grafana.example.com"
    alerts_plan = plan_grafana_alerts(base)
    assert len(alerts_plan) == 1
    assert alerts_plan[0].target == f"{base}/api/v1/provisioning/alert-rules"

    export_plan = plan_grafana_dashboards_export(base, "dash-123")
    assert len(export_plan) == 1
    assert export_plan[0].target == f"{base}/api/dashboards/uid/dash-123"

    import_plan = plan_grafana_dashboards_import(base, Path("dashboard.json"), folder_id=42)
    assert len(import_plan) == 1
    assert import_plan[0].method == "POST"
    assert import_plan[0].target == f"{base}/api/dashboards/db"

    list_plan = plan_grafana_dashboards_list(base)
    assert len(list_plan) == 1
    assert "api/search" in list_plan[0].target

    sync_plan = plan_grafana_dashboards_sync(base, [Path("d1.json"), Path("d2.json")])
    assert len(sync_plan) == 2
    assert all(p.target == f"{base}/api/dashboards/db" for p in sync_plan)

    ds_plan = plan_grafana_datasources(base)
    assert len(ds_plan) == 1
    assert ds_plan[0].target == f"{base}/api/datasources"

    search_plan = plan_grafana_search(base, "prod")
    assert len(search_plan) == 1
    assert search_plan[0].target == f"{base}/api/search?query=prod"


def test_prometheus_plans() -> None:
    """Test Prometheus plan builders."""
    base = "https://prometheus.example.com"
    query_plan = plan_prometheus_query(base, "up", at="2026-10-31T00:00:00Z")
    assert len(query_plan) == 1
    assert "api/v1/query" in query_plan[0].target
    assert "query=up" in query_plan[0].target

    query_range_plan = plan_prometheus_query_range(base, "rate(http[5m])", "1h", "now", "15s")
    assert len(query_range_plan) == 1
    assert "api/v1/query_range" in query_range_plan[0].target

    analyze_plan = plan_prometheus_analyze(base, "up", "1h", "now", "15s")
    assert len(analyze_plan) == 1
    assert "api/v1/query_range" in analyze_plan[0].target

    rules_plan = plan_prometheus_rules(base)
    assert len(rules_plan) == 1
    assert rules_plan[0].target == f"{base}/api/v1/rules"

    targets_plan = plan_prometheus_targets(base)
    assert len(targets_plan) == 1
    assert targets_plan[0].target == f"{base}/api/v1/targets"


def test_telemetry_plans() -> None:
    """Test Telemetry plan builders."""
    status_plan = plan_telemetry_status("http://otel.example.com:4318")
    assert len(status_plan) >= 1
    assert "otel.example.com:4318" in status_plan[0].target

    connect_plan = plan_telemetry_connect(None, "monitoring", "otel-collector", True)
    assert len(connect_plan) >= 1
    assert any("kubectl" in p.argv or p.method == "kubectl" for p in connect_plan)

    test_plan = plan_telemetry_test("test-span", "http://otel.example.com:4318", logfire=True)
    assert len(test_plan) >= 1
    assert "v1/traces" in test_plan[0].target

    profile_plan = plan_telemetry_profile(
        "devops config show", None, "http://tempo.example.com:3200"
    )
    assert len(profile_plan) >= 1
    assert any("config" in " ".join(p.argv) for p in profile_plan if p.argv)

    semconv_plan = plan_telemetry_semconv_refresh("abc1234")
    assert len(semconv_plan) == 1
    assert semconv_plan[0].method == "weaver"
    assert any("abc1234" in arg for arg in semconv_plan[0].argv)


def test_dry_run_cli_executions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify CLI invocations in dry run succeed and make no external network calls."""

    def fail_socket(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Network socket opened during dry run")

    def fail_http(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("HTTP request made during dry run")

    def fail_subprocess(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Subprocess invoked during dry run")

    monkeypatch.setattr(socket.socket, "connect", fail_socket)
    monkeypatch.setattr(httpx2.Client, "send", fail_http)
    monkeypatch.setattr(httpx2.AsyncClient, "send", fail_http)
    monkeypatch.setattr(subprocess, "Popen", fail_subprocess)
    monkeypatch.setattr(subprocess, "run", fail_subprocess)
    monkeypatch.setattr(subprocess, "check_output", fail_subprocess)
    monkeypatch.setattr(subprocess, "check_call", fail_subprocess)

    # 1. dashboard / tui
    res = runner.invoke(app, ["dashboard", "--dry-run"])
    assert res.exit_code == 0, f"dashboard --dry-run failed: {res.output}"
    assert "dashboard" in res.output
    assert "kubectl" in res.output

    res_tui = runner.invoke(app, ["tui", "--dry-run"])
    assert res_tui.exit_code == 0, f"tui --dry-run failed: {res_tui.output}"
    assert "dashboard" in res_tui.output
    assert "kubectl" in res_tui.output

    # 2. grafana alerts
    res = runner.invoke(app, ["grafana", "alerts", "--dry-run"])
    assert res.exit_code == 0, f"grafana alerts --dry-run failed: {res.output}"
    assert "provisioning/alert-rules" in res.output

    # 3. grafana dashboards export
    res = runner.invoke(app, ["grafana", "dashboards", "export", "uid-1", "--dry-run"])
    assert res.exit_code == 0, f"grafana dashboards export --dry-run failed: {res.output}"
    assert "api/dashboards/uid/uid-1" in res.output

    # 4. grafana dashboards import
    dash_file = tmp_path / "dash.json"
    dash_file.write_text('{"dashboard": {"title": "Test"}}', encoding="utf-8")
    res = runner.invoke(app, ["grafana", "dashboards", "import", str(dash_file), "--dry-run"])
    assert res.exit_code == 0, f"grafana dashboards import --dry-run failed: {res.output}"
    assert "api/dashboards/db" in res.output

    # 5. grafana dashboards lint (no-external-request: should run normally and find no json)
    empty_dir = tmp_path / "dashboards"
    empty_dir.mkdir()
    res = runner.invoke(app, ["grafana", "dashboards", "lint", str(empty_dir)])
    assert res.exit_code == 0, f"grafana dashboards lint failed: {res.output}"

    # 6. grafana dashboards list
    res = runner.invoke(app, ["grafana", "dashboards", "list", "--dry-run"])
    assert res.exit_code == 0, f"grafana dashboards list --dry-run failed: {res.output}"
    assert "api/search" in res.output

    # 7. grafana dashboards sync
    res = runner.invoke(
        app, ["grafana", "dashboards", "sync", "--dir", str(empty_dir), "--dry-run"]
    )
    assert res.exit_code == 0, f"grafana dashboards sync --dry-run failed: {res.output}"

    # 8. grafana datasources
    res = runner.invoke(app, ["grafana", "datasources", "--dry-run"])
    assert res.exit_code == 0, f"grafana datasources --dry-run failed: {res.output}"
    assert "api/datasources" in res.output

    # 9. grafana search
    res = runner.invoke(app, ["grafana", "search", "--query", "dash", "--dry-run"])
    assert res.exit_code == 0, f"grafana search --dry-run failed: {res.output}"
    assert "api/search" in res.output

    # 10. prometheus query
    res = runner.invoke(app, ["prometheus", "query", "up", "--dry-run"])
    assert res.exit_code == 0, f"prometheus query --dry-run failed: {res.output}"
    assert "api/v1/query" in res.output

    # 11. prometheus query-range
    res = runner.invoke(app, ["prometheus", "query-range", "up", "--dry-run"])
    assert res.exit_code == 0, f"prometheus query-range --dry-run failed: {res.output}"
    assert "api/v1/query_range" in res.output

    # 12. prometheus analyze
    res = runner.invoke(app, ["prometheus", "analyze", "up", "--dry-run"])
    assert res.exit_code == 0, f"prometheus analyze --dry-run failed: {res.output}"
    assert "api/v1/query_range" in res.output

    # 13. prometheus rules
    res = runner.invoke(app, ["prometheus", "rules", "--dry-run"])
    assert res.exit_code == 0, f"prometheus rules --dry-run failed: {res.output}"
    assert "api/v1/rules" in res.output

    # 14. prometheus targets
    res = runner.invoke(app, ["prometheus", "targets", "--dry-run"])
    assert res.exit_code == 0, f"prometheus targets --dry-run failed: {res.output}"
    assert "api/v1/targets" in res.output

    # 15. telemetry connect
    res = runner.invoke(app, ["telemetry", "connect", "--dry-run"])
    assert res.exit_code == 0, f"telemetry connect --dry-run failed: {res.output}"
    assert "kubectl" in res.output

    # 16. telemetry logfire (no-external-request: local status)
    res = runner.invoke(app, ["telemetry", "logfire"])
    assert res.exit_code == 0, f"telemetry logfire failed: {res.output}"

    # 17. telemetry open-ui (no-external-request: local display)
    res = runner.invoke(app, ["telemetry", "open-ui"])
    assert res.exit_code == 0, f"telemetry open-ui failed: {res.output}"

    # 18. telemetry profile
    res = runner.invoke(app, ["telemetry", "profile", "devops config show", "--dry-run"])
    assert res.exit_code == 0, f"telemetry profile --dry-run failed: {res.output}"

    # 19. telemetry semconv refresh
    res = runner.invoke(app, ["telemetry", "semconv", "refresh", "--commit", "main", "--dry-run"])
    assert res.exit_code == 0, f"telemetry semconv refresh --dry-run failed: {res.output}"
    assert "weaver" in res.output

    # 20. telemetry status
    res = runner.invoke(app, ["telemetry", "status", "--dry-run"])
    assert res.exit_code == 0, f"telemetry status --dry-run failed: {res.output}"

    # 21. telemetry test
    res = runner.invoke(app, ["telemetry", "test", "--dry-run"])
    assert res.exit_code == 0, f"telemetry test --dry-run failed: {res.output}"
    assert "v1/traces" in res.output
