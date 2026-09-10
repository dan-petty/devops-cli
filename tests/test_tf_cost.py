"""Unit tests for OpenTofu / Terraform Infracost FinOps cloud cost estimation and reporting."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.tf import app
from devops_cli.models.tf import TFCostBreakdownResult
from devops_cli.tf.cost import (
    parse_infracost_breakdown,
    parse_infracost_diff,
    run_infracost_breakdown,
    run_infracost_diff,
    validate_cost_budget,
)

runner = CliRunner()

_SAMPLE_BREAKDOWN_JSON = json.dumps(
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

_SAMPLE_DIFF_JSON = json.dumps(
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


def test_parse_infracost_breakdown() -> None:
    """Verify deserialization of Infracost breakdown JSON output."""
    res = parse_infracost_breakdown(_SAMPLE_BREAKDOWN_JSON, directory="tf")
    assert res.currency == "USD"
    assert res.total_monthly_cost == 108.00
    assert res.total_hourly_cost == 0.15
    assert len(res.resources) == 2
    assert res.resources[0].name == "aws_instance.web"
    assert res.resources[0].monthly_cost == 36.00
    assert res.resources[1].name == "aws_nat_gateway.gw"


def test_parse_infracost_diff() -> None:
    """Verify deserialization of Infracost diff JSON output with past and delta monthly cost."""
    res = parse_infracost_diff(_SAMPLE_DIFF_JSON, directory="tf")
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


def test_tf_cost_command_breakdown(tmp_path: Path) -> None:
    """Verify devops tf cost breakdown command with mock execution."""
    result = runner.invoke(app, ["cost", "breakdown", str(tmp_path), "--mock"])
    assert result.exit_code == 0
    assert "Monthly Cost" in result.output or "Cloud Cost Breakdown" in result.output


def test_tf_cost_command_breakdown_json(tmp_path: Path) -> None:
    """Verify devops tf cost breakdown with --json output."""
    result = runner.invoke(app, ["cost", "breakdown", str(tmp_path), "--mock", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "total_monthly_cost" in data
    assert data["source"] == "mock"


def test_tf_cost_command_diff(tmp_path: Path) -> None:
    """Verify devops tf cost diff command with mock execution."""
    result = runner.invoke(app, ["cost", "diff", str(tmp_path), "--mock"])
    assert result.exit_code == 0
    assert "Diff" in result.output or "Cost Diff" in result.output


def test_tf_cost_command_budget_failure(tmp_path: Path) -> None:
    """Verify devops tf cost fails with exit code 1 when budget is exceeded."""
    result = runner.invoke(
        app,
        ["cost", "breakdown", str(tmp_path), "--mock", "--max-monthly-cost", "1.00"],
    )
    assert result.exit_code == 1
    assert "exceeded" in result.output.lower() or "budget" in result.output.lower()


def test_tf_cost_command_dry_run(tmp_path: Path) -> None:
    """Verify devops tf cost respects global dry run."""
    with patch("devops_cli.commands.tf.is_dry_run", return_value=True):
        result = runner.invoke(app, ["cost", "breakdown", str(tmp_path)])
        assert result.exit_code == 0
        assert "devops tf cost" in result.output


def test_tf_cost_estimate_mcp_tool(tmp_path: Path) -> None:
    """Verify FastMCP tool tf_cost_estimate produces valid JSON output."""
    from devops_cli.ai.mcp.server import tf_cost_estimate

    out = tf_cost_estimate(directory=str(tmp_path), mock=True)
    assert "total_monthly_cost" in out


def test_run_infracost_breakdown_subprocess(tmp_path: Path) -> None:
    """Verify infracost breakdown with subprocess success and failure."""
    from unittest.mock import MagicMock

    with (
        patch("devops_cli.tf.cost.check_binary", return_value=True),
        patch("devops_cli.tf.cost.run_subprocess") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout=_SAMPLE_BREAKDOWN_JSON)
        res = run_infracost_breakdown(tmp_path, offline_mock=False)
        assert res.total_monthly_cost == 108.00
        assert res.source == "infracost"

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        res_err = run_infracost_breakdown(tmp_path, offline_mock=False)
        assert res_err.source == "infracost_error"


def test_run_infracost_diff_subprocess(tmp_path: Path) -> None:
    """Verify infracost diff with subprocess success and failure."""
    from unittest.mock import MagicMock

    with (
        patch("devops_cli.tf.cost.check_binary", return_value=True),
        patch("devops_cli.tf.cost.run_subprocess") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout=_SAMPLE_DIFF_JSON)
        res = run_infracost_diff(tmp_path, offline_mock=False)
        assert res.diff_monthly_cost == 36.00
        assert res.source == "infracost"

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        res_err = run_infracost_diff(tmp_path, offline_mock=False)
        assert res_err.source == "infracost_error"
