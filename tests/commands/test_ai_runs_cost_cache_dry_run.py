"""Tests for dry-run request plans and classifications across 21 AI runs, cost, and cache commands.

Issue #2245: The dry-run rule (#412) states that a dry run makes no external request and
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
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

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


@pytest.fixture(autouse=True)
def guard_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no real socket, subprocess, Valkey, or HTTP call executes during dry-run tests."""
    real_run = subprocess.run
    real_popen = subprocess.Popen
    real_check_output = subprocess.check_output

    def _block_socket(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Network socket call attempted during dry-run preview")

    def _block_subprocess(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        cmd_seq = cmd if isinstance(cmd, (list, tuple)) else [cmd]
        first = str(cmd_seq[0]) if cmd_seq else ""
        if Path(first).name == "git":
            return real_run(cmd, *args, **kwargs)
        raise AssertionError(f"Subprocess execution attempted during dry-run preview: {cmd}")

    def _block_popen(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        cmd_seq = cmd if isinstance(cmd, (list, tuple)) else [cmd]
        first = str(cmd_seq[0]) if cmd_seq else ""
        if Path(first).name == "git":
            return real_popen(cmd, *args, **kwargs)
        raise AssertionError(f"Subprocess execution attempted during dry-run preview: {cmd}")

    def _block_check_output(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        cmd_seq = cmd if isinstance(cmd, (list, tuple)) else [cmd]
        first = str(cmd_seq[0]) if cmd_seq else ""
        if Path(first).name == "git":
            return real_check_output(cmd, *args, **kwargs)
        raise AssertionError(f"Subprocess execution attempted during dry-run preview: {cmd}")

    def _block_httpx(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("HTTP request attempted during dry-run preview")

    monkeypatch.setattr(socket.socket, "connect", _block_socket)
    monkeypatch.setattr(subprocess, "Popen", _block_popen)
    monkeypatch.setattr(subprocess, "run", _block_subprocess)
    monkeypatch.setattr(subprocess, "check_output", _block_check_output)
    monkeypatch.setattr(httpx2.Client, "send", _block_httpx)
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", _block_httpx)


def test_dry_run_classes_decorated() -> None:
    """Verify that each command callback is decorated with its assigned dry-run class."""
    for name, callback, _ in REQUEST_PLAN_COMMANDS:
        assert get_dry_run_class(callback) == "request-plan", (
            f"Expected {name} to have dry-run class 'request-plan'"
        )

    for name, callback, _ in LOCAL_PREVIEW_COMMANDS:
        assert get_dry_run_class(callback) == "no-external-request", (
            f"Expected {name} to have dry-run class 'no-external-request'"
        )

    for name, callback, _ in NO_EXTERNAL_REQUEST_COMMANDS:
        assert get_dry_run_class(callback) == "no-external-request", (
            f"Expected {name} to have dry-run class 'no-external-request'"
        )


def test_all_21_commands_removed_from_gaps() -> None:
    """Verify all 21 commands have been excised from tests/fixtures/dry_run_gaps.json."""
    gaps_path = Path("tests/fixtures/dry_run_gaps.json")
    assert gaps_path.exists()
    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))

    expected_removed = (
        [name for name, _, _ in REQUEST_PLAN_COMMANDS]
        + [name for name, _, _ in LOCAL_PREVIEW_COMMANDS]
        + [name for name, _, _ in NO_EXTERNAL_REQUEST_COMMANDS]
    )

    for cmd_path in set(expected_removed):
        assert cmd_path not in gaps, f"Command '{cmd_path}' should be removed from gaps"


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_run_cleanly(name: str, callback: Any, argv: list[str]) -> None:
    """Execute each request-plan command with --dry-run and verify clean exit and plan output."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"{name} failed with {result.output}"
    assert "Plan for" in result.output, (
        f"Expected 'Plan for' header in {name} output, got: {result.output}"
    )


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_flag_order_global_dry_run(name: str, callback: Any, argv: list[str]) -> None:
    """Test global flag order: devops --dry-run <command>."""
    sub_args = [arg for arg in argv if arg != "--dry-run"]
    global_argv = ["--dry-run", *sub_args]
    result = runner.invoke(app, global_argv)
    assert result.exit_code == 0, f"Global --dry-run failed for {name} with: {result.output}"
    assert "Plan for" in result.output, (
        f"Expected 'Plan for' header in global dry-run {name}, got: {result.output}"
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
