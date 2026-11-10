"""The cost check of a plan that builds its own code accepts every unit of elapsed time.

Rule 3 of `AGENTS.md` asks for the tokens to build, keep and fix the code, and the elapsed time. A
plan states the time in hours, in days or in weeks, with a digit or a number word.
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.stage.stage_change import content_problems
from tests.support.builders import make_stage_proposal


@pytest.mark.parametrize(
    "cost",
    [
        "Written cost: about 45k tokens to build, 8k tokens each month to keep, and 3 days.",
        "Cost: 80k tokens and about two days of elapsed time.",
        "Cost: 120k tokens, 1.5 weeks.",
        "Cost: 20k tokens and one hour.",
        "Cost: 20k tokens and Twelve Weeks.",
    ],
)
def test_a_cost_with_a_time_in_days_weeks_or_words_is_accepted(cost: str) -> None:
    plan = make_stage_proposal(builds_own=True, existing_tool=cost)

    assert content_problems(plan) == []


@pytest.mark.parametrize(
    "cost",
    [
        "Cost: 80k tokens and some days.",
        "Cost: 80k tokens and a lot of time.",
        "Cost: two days and no count of tokens.",
        "Cost: 80k tokens and 3 daylights.",
    ],
)
def test_a_cost_with_no_count_of_time_or_of_tokens_is_still_refused(cost: str) -> None:
    plan = make_stage_proposal(builds_own=True, existing_tool=cost)

    assert any("builds_own is true" in p for p in content_problems(plan))
