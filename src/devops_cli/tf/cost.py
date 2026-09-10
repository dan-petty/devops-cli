"""Infracost FinOps cloud cost estimation, diff analysis, and budget validation engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from devops_cli.core.binaries import check_binary
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import DependencyError, SubprocessError, ToolExecutionError
from devops_cli.models.tf import TFCostBreakdownResult, TFCostResource

if TYPE_CHECKING:
    from devops_cli.output.models import TablePayload


def _extract_resources(
    project_data: dict[str, Any], key: str = "breakdown"
) -> list[TFCostResource]:
    """Extract resource line items from Infracost project JSON dictionary."""
    section = project_data.get(key, {})
    raw_resources = section.get("resources", [])
    results: list[TFCostResource] = []
    for item in raw_resources:
        try:
            hourly = float(item.get("hourlyCost") or 0.0)
            monthly = float(item.get("monthlyCost") or 0.0)
        except ValueError, TypeError:
            hourly = 0.0
            monthly = 0.0
        results.append(
            TFCostResource(
                name=str(item.get("name", "")),
                resource_type=str(item.get("resourceType", "")),
                hourly_cost=hourly,
                monthly_cost=monthly,
            )
        )
    return results


def parse_infracost_breakdown(
    json_data: str | dict[str, Any], directory: str = "tf"
) -> TFCostBreakdownResult:
    """Parse Infracost breakdown JSON output into structured TFCostBreakdownResult."""
    try:
        data = json.loads(json_data) if isinstance(json_data, str) else json_data
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object dictionary, got {type(data).__name__}")
        currency = str(data.get("currency", "USD"))
        total_hourly = float(data.get("totalHourlyCost") or 0.0)
        total_monthly = float(data.get("totalMonthlyCost") or 0.0)

        resources: list[TFCostResource] = []
        for proj in data.get("projects", []):
            resources.extend(_extract_resources(proj, key="breakdown"))

        return TFCostBreakdownResult(
            directory=directory,
            currency=currency,
            total_hourly_cost=total_hourly,
            total_monthly_cost=total_monthly,
            resources=resources,
            source="infracost",
            raw_json=data,
        )
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        raise ToolExecutionError(
            f"Failed to parse Infracost breakdown output: {exc}",
            tool_name="infracost",
        ) from exc


def parse_infracost_diff(
    json_data: str | dict[str, Any], directory: str = "tf"
) -> TFCostBreakdownResult:
    """Parse Infracost diff JSON output with delta and previous baseline cost."""
    try:
        data = json.loads(json_data) if isinstance(json_data, str) else json_data
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object dictionary, got {type(data).__name__}")
        currency = str(data.get("currency", "USD"))
        total_hourly = float(data.get("totalHourlyCost") or 0.0)
        total_monthly = float(data.get("totalMonthlyCost") or 0.0)

        past_monthly = (
            float(data["pastTotalMonthlyCost"]) if "pastTotalMonthlyCost" in data else None
        )
        diff_monthly = (
            float(data["diffTotalMonthlyCost"]) if "diffTotalMonthlyCost" in data else None
        )

        resources: list[TFCostResource] = []
        for proj in data.get("projects", []):
            resources.extend(_extract_resources(proj, key="diff"))

        return TFCostBreakdownResult(
            directory=directory,
            currency=currency,
            total_hourly_cost=total_hourly,
            total_monthly_cost=total_monthly,
            past_monthly_cost=past_monthly,
            diff_monthly_cost=diff_monthly,
            resources=resources,
            source="infracost",
            raw_json=data,
        )
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        raise ToolExecutionError(
            f"Failed to parse Infracost diff output: {exc}",
            tool_name="infracost",
        ) from exc


def validate_cost_budget(
    cost: TFCostBreakdownResult, max_monthly_cost: float | None = None
) -> bool:
    """Validate estimated monthly cost against maximum budget threshold."""
    if max_monthly_cost is None:
        return True
    cost.budget_exceeded = cost.total_monthly_cost > max_monthly_cost
    return not cost.budget_exceeded


def run_infracost_breakdown(
    directory: Path | str,
    offline_mock: bool = False,
) -> TFCostBreakdownResult:
    """Execute Infracost breakdown or return deterministic offline mock."""
    target_dir = Path(directory)
    if offline_mock:
        mock_resources = [
            TFCostResource(
                name="aws_instance.web",
                resource_type="aws_instance",
                hourly_cost=0.05,
                monthly_cost=36.00,
            ),
            TFCostResource(
                name="aws_nat_gateway.gw",
                resource_type="aws_nat_gateway",
                hourly_cost=0.10,
                monthly_cost=72.00,
            ),
        ]
        return TFCostBreakdownResult(
            directory=str(target_dir),
            currency="USD",
            total_hourly_cost=0.15,
            total_monthly_cost=108.00,
            resources=mock_resources,
            source="mock",
        )

    if not check_binary("infracost"):
        raise DependencyError(
            "infracost",
            install_hint="Install Infracost CLI or run with --mock for deterministic offline estimates.",
        )

    cmd = ["infracost", "breakdown", "--path", str(target_dir), "--format", "json"]
    proc = run_subprocess(
        cmd,
        cwd=target_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SubprocessError(
            f"Infracost breakdown failed with exit code {proc.returncode}: {proc.stderr.strip()}",
            command=cmd,
            exit_code=proc.returncode,
            stderr=proc.stderr.strip(),
        )
    return parse_infracost_breakdown(proc.stdout, directory=str(target_dir))


def run_infracost_diff(
    directory: Path | str,
    compare_to: Path | str | None = None,
    offline_mock: bool = False,
) -> TFCostBreakdownResult:
    """Execute Infracost diff against state or baseline file, or return deterministic offline mock."""
    target_dir = Path(directory)
    if offline_mock:
        mock_resources = [
            TFCostResource(
                name="aws_instance.worker",
                resource_type="aws_instance",
                hourly_cost=0.05,
                monthly_cost=36.00,
            ),
        ]
        return TFCostBreakdownResult(
            directory=str(target_dir),
            currency="USD",
            total_hourly_cost=0.20,
            total_monthly_cost=144.00,
            past_monthly_cost=108.00,
            diff_monthly_cost=36.00,
            resources=mock_resources,
            source="mock",
        )

    if not check_binary("infracost"):
        raise DependencyError(
            "infracost",
            install_hint="Install Infracost CLI or run with --mock for deterministic offline estimates.",
        )

    cmd = ["infracost", "diff", "--path", str(target_dir), "--format", "json"]
    if compare_to:
        cmd.extend(["--compare-to", str(compare_to)])

    proc = run_subprocess(
        cmd,
        cwd=target_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SubprocessError(
            f"Infracost diff failed with exit code {proc.returncode}: {proc.stderr.strip()}",
            command=cmd,
            exit_code=proc.returncode,
            stderr=proc.stderr.strip(),
        )
    return parse_infracost_diff(proc.stdout, directory=str(target_dir))


def render_cost_table(cost: TFCostBreakdownResult, title: str | None = None) -> TablePayload:
    """Render a structured TablePayload displaying resource cost breakdown."""
    from devops_cli.output import format_tf_cost_table

    return format_tf_cost_table(cost, title=title)
