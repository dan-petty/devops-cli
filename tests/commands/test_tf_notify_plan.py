"""Tests of `devops tf notify-plan`: it prints the plan comment and sends no request."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _comment(result: str, plan_text: str) -> str:
    return (
        "### 🚀 OpenTofu / Terraform Plan Summary\n"
        f"**Result:** `{result}`\n"
        "\n"
        "<details><summary>Click to expand execution plan details</summary>\n"
        "\n"
        "```terraform\n"
        f"{plan_text}\n"
        "```\n"
        "\n"
        "</details>\n"
    )


def test_notify_plan_prints_the_comment_for_a_pull_request(
    cli: Callable[..., Any], tmp_path: Path
) -> None:
    """The comment holds the plan text, and the pull request number goes only into the output."""
    plan_file = tmp_path / "plan.txt"
    plan_file.write_text("No changes.", encoding="utf-8")

    result = cli("tf", "notify-plan", "--plan-file", str(plan_file), "--pr", "42", "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "pr": 42,
        "adds": 0,
        "changes": 0,
        "destroys": 0,
        "comment": _comment("+0 ~0 -0", "No changes."),
    }


def test_notify_plan_prints_the_sample_plan_with_no_plan_file(cli: Callable[..., Any]) -> None:
    """With no plan file, the command refuses the call and names the option."""
    result = cli("tf", "notify-plan", "--json")

    assert result.exit_code != 0
    assert "--plan-file" in result.output
    assert "+2 ~1 -0" not in result.output


def test_notify_plan_counts_the_segments_of_the_summary_line(
    cli: Callable[..., Any], tmp_path: Path
) -> None:
    plan_file = tmp_path / "plan.txt"
    plan_file.write_text("Plan: 5 to add, 3 to change, 1 to destroy.", encoding="utf-8")

    result = cli("tf", "notify-plan", "--plan-file", str(plan_file), "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert (payload["adds"], payload["changes"], payload["destroys"]) == (5, 3, 1)
    assert "**Result:** `+5 ~3 -1`" in payload["comment"]


def test_an_import_segment_changes_no_count(cli: Callable[..., Any], tmp_path: Path) -> None:
    plan_file = tmp_path / "plan.txt"
    plan_file.write_text(
        "Plan: 1 to import, 0 to add, 2 to change, 0 to destroy.", encoding="utf-8"
    )

    result = cli("tf", "notify-plan", "--plan-file", str(plan_file), "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert (payload["adds"], payload["changes"], payload["destroys"]) == (0, 2, 0)
    assert "**Result:** `+0 ~2 -0`" in payload["comment"]


def test_notify_plan_refuses_a_missing_plan_file(cli: Callable[..., Any], tmp_path: Path) -> None:
    missing = tmp_path / "no-such-file.txt"

    result = cli("tf", "notify-plan", "--plan-file", str(missing), "--json")

    assert result.exit_code != 0
    assert "no-such-file.txt" in result.output
    assert "+2 ~1 -0" not in result.output


def test_the_table_output_holds_the_counts_of_the_file(
    cli: Callable[..., Any], tmp_path: Path
) -> None:
    plan_file = tmp_path / "plan.txt"
    plan_file.write_text("Plan: 5 to add, 3 to change, 1 to destroy.", encoding="utf-8")

    result = cli("tf", "notify-plan", "--plan-file", str(plan_file))

    assert result.exit_code == 0, result.output
    assert "+5 ~3 -1" in result.output
    assert "+2 ~1 -0" not in result.output
