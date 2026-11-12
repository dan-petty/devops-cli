"""Tests for dry-run request plans and classifications across 21 AI runs, cost, and cache commands.

Issue #2245: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ai_cache import (
    cache_clear,
    cache_status,
)
from devops_cli.commands.ai_cost import (
    cost_default,
    cost_list_pricing,
    cost_payback,
    cost_payoff,
    cost_prometheus,
    cost_report,
    cost_reset,
    cost_roi,
    cost_set_price,
    cost_update_pricing,
)
from devops_cli.commands.ai_runs import (
    baseline_list_cmd,
    baseline_set_cmd,
    baseline_show_cmd,
    check_cmd,
    compare_cmd,
    connect_cmd,
    list_cmd,
    reindex_cmd,
    show_cmd,
)
from devops_cli.main import app
from tests.support.dry_run_classes import misclassified

pytestmark = pytest.mark.usefixtures("refuse_requests")

runner = CliRunner()

REQUEST_PLAN_COMMANDS = [
    ("ai cost update-pricing", cost_update_pricing, ["ai", "cost", "update-pricing", "--dry-run"]),
    (
        "ai runs baseline set",
        baseline_set_cmd,
        ["ai", "runs", "baseline", "set", "test-run", "--dry-run"],
    ),
    (
        "ai runs baseline show",
        baseline_show_cmd,
        ["ai", "runs", "baseline", "show", "test-sub", "--dry-run"],
    ),
    ("ai runs check", check_cmd, ["ai", "runs", "check", "test-run", "--dry-run"]),
    ("ai runs compare", compare_cmd, ["ai", "runs", "compare", "run-a", "run-b", "--dry-run"]),
    ("ai runs connect", connect_cmd, ["ai", "runs", "connect", "--dry-run"]),
    ("ai runs reindex", reindex_cmd, ["ai", "runs", "reindex", "--dry-run"]),
    ("ai runs show", show_cmd, ["ai", "runs", "show", "test-run", "--dry-run"]),
]

LOCAL_PREVIEW_COMMANDS = [
    ("ai cost reset", cost_reset, ["ai", "cost", "reset", "--dry-run"]),
    (
        "ai cost set-price",
        cost_set_price,
        ["ai", "cost", "set-price", "gpt-4o", "2.50", "10.00", "--dry-run"],
    ),
]

NO_EXTERNAL_REQUEST_COMMANDS = [
    ("ai cache clear", cache_clear, ["--dry-run", "ai", "cache", "clear"]),
    ("ai cache status", cache_status, ["--dry-run", "ai", "cache", "status"]),
    ("ai cost", cost_default, ["--dry-run", "ai", "cost"]),
    ("ai cost list-pricing", cost_list_pricing, ["--dry-run", "ai", "cost", "list-pricing"]),
    ("ai cost payback", cost_payback, ["--dry-run", "ai", "cost", "payback"]),
    ("ai cost payoff", cost_payoff, ["--dry-run", "ai", "cost", "payoff"]),
    ("ai cost prometheus", cost_prometheus, ["--dry-run", "ai", "cost", "prometheus"]),
    ("ai cost report", cost_report, ["--dry-run", "ai", "cost", "report"]),
    ("ai cost roi", cost_roi, ["--dry-run", "ai", "cost", "roi"]),
    ("ai runs baseline list", baseline_list_cmd, ["--dry-run", "ai", "runs", "baseline", "list"]),
    ("ai runs list", list_cmd, ["--dry-run", "ai", "runs", "list"]),
]


def test_commands_carry_their_dry_run_class() -> None:
    """Run commands carry request-plan; cost, cache and the local previews carry no-external-request."""
    assert misclassified(REQUEST_PLAN_COMMANDS, "request-plan") == {}
    assert misclassified(LOCAL_PREVIEW_COMMANDS, "no-external-request") == {}
    assert misclassified(NO_EXTERNAL_REQUEST_COMMANDS, "no-external-request") == {}


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_run_cleanly(name: str, callback: Any, argv: list[str]) -> None:
    """Execute each request-plan command with --dry-run and verify clean exit and plan output."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"{name} failed with {result.output}"
    assert "Plan for" in result.output, (
        f"Expected 'Plan for' header in {name} output, got: {result.output}"
    )


@pytest.mark.parametrize("name,callback,argv", NO_EXTERNAL_REQUEST_COMMANDS)
def test_no_external_request_commands_run(name: str, callback: Any, argv: list[str]) -> None:
    """Test commands classified as no-external-request run normally without error."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"{name} failed with {result.output}"


@pytest.mark.parametrize("name,callback,argv", LOCAL_PREVIEW_COMMANDS)
def test_local_preview_commands_dry_run(name: str, callback: Any, argv: list[str]) -> None:
    """Test local preview commands with --dry-run execute without writing state."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"{name} failed with {result.output}"
    assert "Would " in result.output or "Dry run: " in result.output, (
        f"Expected dry-run preview indicator in {name}, got: {result.output}"
    )


def test_ai_runs_json_dry_run_formats() -> None:
    """Verify json output formats for ai runs dry runs."""
    res_show = runner.invoke(
        app, ["ai", "runs", "show", "run-123", "--dry-run", "--format", "json"]
    )
    assert res_show.exit_code == 0
    data = json.loads(res_show.output)
    assert data["dry_run"] is True
    assert data["run_id"] == "run-123"
    assert len(data["requests"]) == 1

    res_comp_1 = runner.invoke(
        app, ["ai", "runs", "compare", "run-123", "--dry-run", "--format", "json"]
    )
    assert res_comp_1.exit_code == 0
    data = json.loads(res_comp_1.output)
    assert data["dry_run"] is True
    assert data["run_a"] == "run-123"
    assert data["run_b"] is None
    assert len(data["requests"]) == 2

    res_comp_2 = runner.invoke(
        app, ["ai", "runs", "compare", "run-123", "run-456", "--dry-run", "--format", "json"]
    )
    assert res_comp_2.exit_code == 0
    data = json.loads(res_comp_2.output)
    assert data["dry_run"] is True
    assert data["run_a"] == "run-123"
    assert data["run_b"] == "run-456"
    assert len(data["requests"]) == 2

    res_base_show = runner.invoke(
        app, ["ai", "runs", "baseline", "show", "sub-123", "--dry-run", "--format", "json"]
    )
    assert res_base_show.exit_code == 0
    data = json.loads(res_base_show.output)
    assert data["dry_run"] is True
    assert data["subject_or_run"] == "sub-123"
    assert len(data["requests"]) == 1

    res_check = runner.invoke(
        app, ["ai", "runs", "check", "run-123", "--dry-run", "--format", "json"]
    )
    assert res_check.exit_code == 0
    data = json.loads(res_check.output)
    assert data["dry_run"] is True
    assert data["run_id"] == "run-123"
    assert data["baseline_id"] is None
    assert len(data["requests"]) == 2

    res_check_base = runner.invoke(
        app,
        [
            "ai",
            "runs",
            "check",
            "run-123",
            "--baseline",
            "base-999",
            "--dry-run",
            "--format",
            "json",
        ],
    )
    assert res_check_base.exit_code == 0
    data = json.loads(res_check_base.output)
    assert data["dry_run"] is True
    assert data["run_id"] == "run-123"
    assert data["baseline_id"] == "base-999"
    assert len(data["requests"]) == 2


def test_ai_cost_update_pricing_options(tmp_path: Path) -> None:
    """Verify ai cost update-pricing dry run with reset and local source options."""
    res_reset = runner.invoke(app, ["ai", "cost", "update-pricing", "--reset", "--dry-run"])
    assert res_reset.exit_code == 0
    assert "Plan for" in res_reset.output

    local_prices = tmp_path / "prices.json"
    local_prices.write_text("{}", encoding="utf-8")
    res_file = runner.invoke(
        app, ["ai", "cost", "update-pricing", "--source", str(local_prices), "--dry-run"]
    )
    assert res_file.exit_code == 0
    assert "Plan for" in res_file.output


def test_ai_spend_alias_commands() -> None:
    """Verify alias 'ai spend' commands run identically with dry run."""
    res_spend = runner.invoke(app, ["--dry-run", "ai", "spend"])
    assert res_spend.exit_code == 0

    res_report = runner.invoke(app, ["--dry-run", "ai", "spend", "report"])
    assert res_report.exit_code == 0

    res_pricing = runner.invoke(app, ["--dry-run", "ai", "spend", "list-pricing"])
    assert res_pricing.exit_code == 0

    res_update = runner.invoke(app, ["ai", "spend", "update-pricing", "--dry-run"])
    assert res_update.exit_code == 0
    assert "Plan for" in res_update.output


def test_local_preview_commands_do_not_mutate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that --dry-run on cost set-price and reset performs zero writes."""
    from devops_cli.ai.spend import ledger as ledger_mod
    from devops_cli.ai.spend import pricing as pricing_mod

    def _fail_set_price(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("set_custom_pricing called during dry run")

    def _fail_reset(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("reset_ledger called during dry run")

    monkeypatch.setattr(pricing_mod.PricingRegistry, "set_custom_pricing", _fail_set_price)
    monkeypatch.setattr(ledger_mod.SpendLedger, "reset_ledger", _fail_reset)

    res_set = runner.invoke(
        app, ["ai", "cost", "set-price", "claude-3-5-sonnet", "3.0", "15.0", "--dry-run"]
    )
    assert res_set.exit_code == 0
    assert "Would configure custom pricing" in res_set.output

    res_reset = runner.invoke(app, ["ai", "cost", "reset", "--dry-run"])
    assert res_reset.exit_code == 0
    assert "Would reset lifetime AI spend ledger records" in res_reset.output
