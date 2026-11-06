"""Tests for `devops tf cost breakdown` and `devops tf cost diff`.

The commands run through `cli`. Infracost is a program: a test scripts its answer on
`process_fake`, or asks for `--mock`, which starts no program.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.support.fakes.process import ProcessAnswer, ProcessFake

_DIFF_JSON = json.dumps(
    {
        "currency": "USD",
        "totalMonthlyCost": "100.00",
        "pastTotalMonthlyCost": "90.00",
        "diffTotalMonthlyCost": "10.00",
        "projects": [],
    }
)


def test_cost_breakdown_prints_the_mock_estimate(cli: Callable[..., Any], tmp_path: Path) -> None:
    """Verify devops tf cost breakdown command with mock execution."""
    result = cli("tf", "cost", "breakdown", str(tmp_path), "--mock")

    assert result.exit_code == 0
    assert "Monthly Cost" in result.output or "Cloud Cost Breakdown" in result.output


def test_cost_breakdown_json_names_its_source(cli: Callable[..., Any], tmp_path: Path) -> None:
    """Verify devops tf cost breakdown with --json output."""
    result = cli("tf", "cost", "breakdown", str(tmp_path), "--mock", "--json")

    data = json.loads(result.output)
    assert (result.exit_code, "total_monthly_cost" in data, data["source"]) == (0, True, "mock")


def test_cost_diff_prints_the_mock_estimate(cli: Callable[..., Any], tmp_path: Path) -> None:
    """Verify devops tf cost diff command with mock execution."""
    result = cli("tf", "cost", "diff", str(tmp_path), "--mock")

    assert result.exit_code == 0
    assert "Diff" in result.output or "Cost Diff" in result.output


def test_cost_breakdown_over_budget_exits_with_one(cli: Callable[..., Any], tmp_path: Path) -> None:
    """Verify devops tf cost fails with exit code 1 when budget is exceeded."""
    result = cli("tf", "cost", "breakdown", str(tmp_path), "--mock", "--max-monthly-cost", "1.00")

    assert result.exit_code == 1
    assert "exceeded" in result.output.lower() or "budget" in result.output.lower()


def test_cost_breakdown_over_budget_json_reports_it(
    cli: Callable[..., Any], tmp_path: Path
) -> None:
    """Verify over-budget result serializes budget_exceeded: true in JSON output."""
    result = cli(
        "tf", "cost", "breakdown", str(tmp_path), "--mock", "--json", "--max-monthly-cost", "1.00"
    )

    data = json.loads(result.output)
    assert (result.exit_code, data["budget_exceeded"], data["total_monthly_cost"] > 1.00) == (
        1,
        True,
        True,
    )


def test_cost_diff_over_budget_json_reports_it(cli: Callable[..., Any], tmp_path: Path) -> None:
    """Verify over-budget diff serializes budget_exceeded: true in JSON output."""
    result = cli(
        "tf", "cost", "diff", str(tmp_path), "--mock", "--json", "--max-monthly-cost", "1.00"
    )

    assert (result.exit_code, json.loads(result.output)["budget_exceeded"]) == (1, True)


def test_cost_diff_hands_the_baseline_to_infracost(
    cli: Callable[..., Any], tmp_path: Path, process_fake: ProcessFake
) -> None:
    """Verify devops tf cost diff passes --compare-to baseline."""
    baseline = tmp_path / "infracost-base.json"
    baseline.write_text("{}", encoding="utf-8")
    process_fake.answer("infracost", ProcessAnswer(stdout=_DIFF_JSON))

    result = cli("tf", "cost", "diff", str(tmp_path), "--compare-to", str(baseline), "--json")

    (call,) = process_fake.calls
    assert (result.exit_code, json.loads(result.output)["diff_monthly_cost"]) == (0, 10.0)
    assert call.argv[call.argv.index("--compare-to") + 1] == str(baseline)


def test_cost_breakdown_under_dry_run_plans_the_request(
    cli: Callable[..., Any], tmp_path: Path, process_fake: ProcessFake
) -> None:
    """Verify devops tf cost respects global dry run and plans request."""
    result = cli("--dry-run", "tf", "cost", "breakdown", str(tmp_path))

    assert (result.exit_code, "infracost breakdown" in result.output, process_fake.calls) == (
        0,
        True,
        [],
    )
