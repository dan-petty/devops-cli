"""Tests for the Infracost cost estimation, diff analysis and budget validation of `tf/cost.py`.

Infracost is a program, so a test scripts its answer on `process_fake` and reads the command that
was started from the fake's `calls`. A host without Infracost is a `PATH` with no program in it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.exceptions import DependencyError, SubprocessError, ToolExecutionError
from devops_cli.models.tf import TFCostBreakdownResult
from devops_cli.tf.cost import (
    parse_infracost_breakdown,
    parse_infracost_diff,
    run_infracost_breakdown,
    run_infracost_diff,
    validate_cost_budget,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake

SAMPLE_BREAKDOWN_JSON = json.dumps(
    {
        "currency": "USD",
        "totalHourlyCost": "0.15",
        "totalMonthlyCost": "108.00",
        "projects": [
            {
                "name": "tf",
                "breakdown": {
                    "resources": [
                        {
                            "name": "aws_instance.web",
                            "resourceType": "aws_instance",
                            "hourlyCost": "0.05",
                            "monthlyCost": "36.00",
                        },
                        {
                            "name": "aws_nat_gateway.gw",
                            "resourceType": "aws_nat_gateway",
                            "hourlyCost": "0.10",
                            "monthlyCost": "72.00",
                        },
                    ]
                },
            }
        ],
    }
)

SAMPLE_DIFF_JSON = json.dumps(
    {
        "currency": "USD",
        "totalHourlyCost": "0.20",
        "totalMonthlyCost": "144.00",
        "pastTotalMonthlyCost": "108.00",
        "diffTotalMonthlyCost": "36.00",
        "projects": [
            {
                "name": "tf",
                "diff": {
                    "resources": [
                        {
                            "name": "aws_instance.worker",
                            "resourceType": "aws_instance",
                            "hourlyCost": "0.05",
                            "monthlyCost": "36.00",
                        }
                    ]
                },
            }
        ],
    }
)


@pytest.fixture
def no_programs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A host on which no program is installed: `PATH` names an empty directory."""
    empty = tmp_path / "no-programs"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))


def test_parse_infracost_breakdown() -> None:
    """Verify deserialization of Infracost breakdown JSON output."""
    res = parse_infracost_breakdown(SAMPLE_BREAKDOWN_JSON, directory="tf")
    assert res.currency == "USD"
    assert res.total_monthly_cost == 108.00
    assert res.total_hourly_cost == 0.15
    assert len(res.resources) == 2
    assert res.resources[0].name == "aws_instance.web"
    assert res.resources[0].monthly_cost == 36.00
    assert res.resources[1].name == "aws_nat_gateway.gw"


def test_parse_infracost_diff() -> None:
    """Verify deserialization of Infracost diff JSON output with past and delta monthly cost."""
    res = parse_infracost_diff(SAMPLE_DIFF_JSON, directory="tf")
    assert res.currency == "USD"
    assert res.total_monthly_cost == 144.00
    assert res.past_monthly_cost == 108.00
    assert res.diff_monthly_cost == 36.00
    assert len(res.resources) == 1
    assert res.resources[0].name == "aws_instance.worker"


def test_validate_cost_budget() -> None:
    """Verify budget threshold assertion passes or fails properly."""
    cost = TFCostBreakdownResult(
        directory="tf",
        currency="USD",
        total_monthly_cost=150.00,
        total_hourly_cost=0.20,
    )
    # Under or equal budget
    assert validate_cost_budget(cost, max_monthly_cost=200.00) is True
    assert cost.budget_exceeded is False

    # Over budget
    assert validate_cost_budget(cost, max_monthly_cost=100.00) is False
    assert cost.budget_exceeded is True

    # No budget set
    assert validate_cost_budget(cost, max_monthly_cost=None) is True


def test_run_infracost_breakdown_offline_mock(tmp_path: Path) -> None:
    """Verify mock execution when Infracost binary is missing or offline mode is requested."""
    res = run_infracost_breakdown(tmp_path, offline_mock=True)
    assert res.source == "mock"
    assert res.total_monthly_cost > 0
    assert len(res.resources) > 0


def test_run_infracost_diff_offline_mock(tmp_path: Path) -> None:
    """Verify mock diff execution when offline."""
    res = run_infracost_diff(tmp_path, offline_mock=True)
    assert res.source == "mock"
    assert res.diff_monthly_cost is not None
    assert len(res.resources) > 0


def test_parse_infracost_malformed_errors() -> None:
    """Verify ToolExecutionError raised on invalid or non-dict JSON output."""
    with pytest.raises(ToolExecutionError, match="Failed to parse Infracost breakdown output"):
        parse_infracost_breakdown("not-json", directory="tf")

    with pytest.raises(ToolExecutionError, match="Failed to parse Infracost breakdown output"):
        parse_infracost_breakdown("[1, 2, 3]", directory="tf")

    with pytest.raises(ToolExecutionError, match="Failed to parse Infracost diff output"):
        parse_infracost_diff("{broken", directory="tf")


@pytest.mark.usefixtures("no_programs")
@pytest.mark.parametrize("run", [run_infracost_breakdown, run_infracost_diff])
def test_a_missing_infracost_binary_raises_dependency_error(
    run: Callable[..., TFCostBreakdownResult], tmp_path: Path
) -> None:
    """Verify DependencyError raised when Infracost binary is missing without --mock."""
    with pytest.raises(DependencyError, match="infracost"):
        run(tmp_path, offline_mock=False)


def test_run_infracost_breakdown_starts_infracost_in_the_directory(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """The breakdown runs `infracost breakdown` in the target directory and parses its JSON."""
    process_fake.answer("infracost", ProcessAnswer(stdout=SAMPLE_BREAKDOWN_JSON))

    res = run_infracost_breakdown(tmp_path, offline_mock=False)

    assert (res.total_monthly_cost, res.source, res.directory) == (
        108.00,
        "infracost",
        str(tmp_path),
    )
    (call,) = process_fake.calls
    assert (call.argv[:2], str(tmp_path) in call.argv, call.cwd) == (
        ("infracost", "breakdown"),
        True,
        tmp_path,
    )


def test_run_infracost_breakdown_failure_carries_the_exit_code_and_stderr(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """A non-zero exit of Infracost raises SubprocessError with its stderr."""
    process_fake.answer("infracost", ProcessAnswer(returncode=1, stderr="infracost auth failed"))

    with pytest.raises(
        SubprocessError, match="Infracost breakdown failed with exit code 1"
    ) as raised:
        run_infracost_breakdown(tmp_path, offline_mock=False)

    assert "infracost auth failed" in str(raised.value)


def test_run_infracost_diff_passes_the_baseline(tmp_path: Path, process_fake: ProcessFake) -> None:
    """The diff runs `infracost diff` with `--compare-to` and parses its JSON."""
    process_fake.answer("infracost", ProcessAnswer(stdout=SAMPLE_DIFF_JSON))

    res = run_infracost_diff(tmp_path, compare_to="base.json", offline_mock=False)

    (call,) = process_fake.calls
    assert (res.diff_monthly_cost, res.source, call.argv[:2]) == (
        36.00,
        "infracost",
        ("infracost", "diff"),
    )
    assert call.argv[call.argv.index("--compare-to") + 1] == "base.json"


def test_run_infracost_diff_failure_carries_the_exit_code(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """A non-zero exit of Infracost raises SubprocessError."""
    process_fake.answer("infracost", ProcessAnswer(returncode=1, stderr="diff failed"))

    with pytest.raises(SubprocessError, match="Infracost diff failed with exit code 1"):
        run_infracost_diff(tmp_path, offline_mock=False)
