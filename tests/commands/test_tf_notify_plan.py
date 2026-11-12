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
    """With no plan file, the comment holds the fixed sample plan."""
    result = cli("tf", "notify-plan", "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "pr": None,
        "adds": 2,
        "changes": 1,
        "destroys": 0,
        "comment": _comment("+2 ~1 -0", "Plan: 2 to add, 1 to change, 0 to destroy."),
    }
