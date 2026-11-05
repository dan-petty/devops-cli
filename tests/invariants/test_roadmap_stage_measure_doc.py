"""The stage measurement section of `docs/ROADMAP_WORKFLOW.md` states what an acceptable score is
and how to find the cheapest model that reaches it (#3207)."""

from __future__ import annotations

import re

import pytest

from tests.support.paths import REPO_ROOT

DOCUMENT = REPO_ROOT / "docs" / "ROADMAP_WORKFLOW.md"


def _section(heading: str) -> str:
    text = DOCUMENT.read_text(encoding="utf-8")
    match = re.search(rf"^### {re.escape(heading)}\n(.*?)(?=^##+ |\Z)", text, re.S | re.M)
    assert match is not None, f"{DOCUMENT.name} has no section {heading!r}"
    return match.group(1)


def test_the_acceptable_score_has_a_recall_threshold_a_good_plan_rule_and_a_live_share() -> None:
    section = _section("What an acceptable stage score is")

    assert "at least 90%" in section
    assert "blocker" in section
    assert "major" in section
    assert "3 good plans" in section
    assert "At least 80%" in section


@pytest.mark.parametrize(
    "needed",
    [
        "`ai.tasks.stage.model`",
        "`DEVOPS_CLI_AI_TASK_STAGE_MODEL`",
        "devops roadmap eval stage --model claude-sonnet-5-5 --no-toolbox",
        "devops roadmap eval verify --model claude-sonnet-5-5",
        "#3066",
        "#3060",
    ],
)
def test_the_baseline_procedure_names_the_setting_the_commands_and_the_parked_work(
    needed: str,
) -> None:
    text = _section("The model of the stage planner") + _section(
        "Find the cheapest model that is acceptable"
    )

    assert needed in text
