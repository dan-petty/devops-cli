"""`devops roadmap stage`: a plan holds no placeholder text, quotes its probe, gives the cost of
its own code and keeps its summary whole (#3200)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.roadmap.stage_change import (
    PLAN_FIELD_MIN_CHARS,
    StageProposal,
    check_proposal,
    content_problems,
    staging_title,
)
from devops_cli.roadmap.stage_eval_cases import DefectType, GateName
from devops_cli.roadmap.stage_eval_gates import gate_for
from devops_cli.roadmap.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

PROBE = "def f(): pass"
TREE = StagedTree(["src/devops_cli/sample.py", "tests/test_sample.py"])


def _check(proposal: StageProposal, **keywords: Any) -> list[str]:
    return check_proposal(proposal, ["comment-thread"], TREE, **keywords)


def test_the_sample_plan_has_no_content_problem() -> None:
    assert content_problems(make_stage_proposal()) == []
    assert _check(make_stage_proposal()) == []


def test_a_why_of_x_is_refused_with_its_field_and_the_least_length() -> None:
    problems = _check(make_stage_proposal(why="x"))

    assert any(
        "of why has 1 characters" in p and f"least is {PLAN_FIELD_MIN_CHARS}" in p for p in problems
    )


def test_a_placeholder_existing_tool_is_refused_with_its_field_and_the_placeholder_rule() -> None:
    problems = _check(make_stage_proposal(existing_tool="todo"))

    assert any("existing_tool is the placeholder `todo`" in p for p in problems)


@pytest.mark.parametrize("text", ["TBD", "x", "None.", "placeholder"])
def test_a_placeholder_word_is_a_placeholder_for_the_rule_of_the_pull_request_form(
    text: str,
) -> None:
    problems = content_problems(make_stage_proposal(why=text))

    assert any("is the placeholder" in p for p in problems)


def test_a_short_real_sentence_is_accepted() -> None:
    assert content_problems(make_stage_proposal(why="No alternative.")) == []


@pytest.mark.parametrize("line", ["x", "ok"])
def test_a_short_line_of_feasibility_is_refused(line: str) -> None:
    problems = content_problems(make_stage_proposal(feasibility=[line]))

    assert any("of feasibility" in p for p in problems)


def test_a_short_decision_and_a_short_task_are_refused_with_their_field() -> None:
    sample = make_stage_proposal()
    group = sample.groups[0].model_copy(update={"implementation": "Do it"})
    decision = {"decision": "Short one", "reason": "A reason that is long enough."}

    problems = content_problems(make_stage_proposal(decisions=[decision], groups=[group]))

    assert [p.split(" has ")[0] for p in problems] == [
        "The text of decision",
        "The text of implementation of group 1",
    ]


def test_a_feasibility_with_no_probe_line_is_refused_when_there_are_probes() -> None:
    problems = content_problems(make_stage_proposal(feasibility=["The function exists."]), [PROBE])

    assert any("feasibility list quotes no line of the probes" in p for p in problems)


def test_a_feasibility_that_quotes_a_probe_line_is_accepted() -> None:
    plan = make_stage_proposal(feasibility=[f"The probe shows {PROBE}."])

    assert content_problems(plan, [PROBE]) == []


def test_a_quote_holds_when_the_white_space_differs() -> None:
    plan = make_stage_proposal(feasibility=["The probe shows `a`   exists at\nthe commit."])

    assert content_problems(plan, ["`a` exists   at the commit"]) == []


def test_a_job_that_read_no_probe_is_not_judged_on_the_quote() -> None:
    assert content_problems(make_stage_proposal(feasibility=["The function exists."])) == []


def test_check_proposal_passes_the_probes_to_the_content_check() -> None:
    plan = make_stage_proposal(feasibility=["The function exists."])

    assert any("quotes no line" in p for p in _check(plan, probes=[PROBE]))
    assert not any("quotes no line" in p for p in _check(plan))


def test_a_plan_that_builds_its_own_code_gives_a_token_count_and_a_time() -> None:
    plan = make_stage_proposal(builds_own=True, existing_tool="Pydantic can set a minimum length.")

    assert any("builds_own is true" in p for p in content_problems(plan))


@pytest.mark.parametrize(
    "cost",
    [
        "Cost to build: about 80k tokens and 4 hours.",
        "1200 tokens, 30 Minutes",
        "1.5K tokens, 2 hours",
    ],
)
def test_a_cost_with_tokens_and_a_time_is_accepted(cost: str) -> None:
    assert content_problems(make_stage_proposal(builds_own=True, existing_tool=cost)) == []


@pytest.mark.parametrize("cost", ["It costs 80k tokens to build.", "It takes 4 hours to build it."])
def test_a_cost_with_only_tokens_or_only_a_time_is_refused(cost: str) -> None:
    plan = make_stage_proposal(builds_own=True, existing_tool=cost)

    assert any("builds_own is true" in p for p in content_problems(plan))


def test_a_plan_that_adopts_a_tool_needs_no_cost() -> None:
    plan = make_stage_proposal(builds_own=False, existing_tool="Pydantic covers the need.")

    assert content_problems(plan) == []


def test_a_summary_over_the_bound_is_refused_by_the_schema() -> None:
    limit = StageProposal.model_json_schema()["properties"]["summary"]["maxLength"]

    with pytest.raises(ValidationError, match=f"limit is {limit}"):
        make_stage_proposal(summary="a" * (limit + 1))


def test_a_summary_that_ends_with_an_ellipsis_is_refused_by_the_schema() -> None:
    with pytest.raises(ValidationError, match=r"ends with `\.\.\.`"):
        make_stage_proposal(summary="Refuse a cut text...")


def test_the_staging_title_holds_the_whole_summary() -> None:
    assert staging_title(3200, "Refuse placeholder text") == (
        "docs(openspec): plan #3200 Refuse placeholder text"
    )


def test_the_replay_has_a_content_gate_for_the_other_type() -> None:
    assert gate_for(DefectType.OTHER) is GateName.CONTENT
