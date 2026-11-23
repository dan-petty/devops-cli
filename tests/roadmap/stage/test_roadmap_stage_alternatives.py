"""`devops roadmap stage`: require a rejected alternative with a fact (#3257)."""

from __future__ import annotations

from datetime import date

from devops_cli.roadmap.stage.stage_change import (
    StageDecision,
    StageRejection,
    content_problems,
    render_change,
)
from tests.support.builders import make_stage_proposal


def test_content_problems_refuses_a_decision_with_no_rejected_alternative() -> None:
    proposal = make_stage_proposal(
        decisions=[StageDecision(decision="Keep the list", reason="It is the simplest fix.")],
        rejected=[],
    )
    problems = content_problems(proposal)
    assert any("Keep the list" in p and "## Rejected alternatives" in p for p in problems)


def test_content_problems_refuses_an_alternative_with_only_an_opinion() -> None:
    proposal = make_stage_proposal(
        decisions=[StageDecision(decision="Keep the list", reason="It is the simplest fix.")],
        rejected=[StageRejection(alternative="A new class", evidence="This option is worse.")],
    )
    problems = content_problems(proposal)
    assert any("A new class" in p for p in problems)


def test_content_problems_accepts_an_alternative_with_a_fact() -> None:
    proposal = make_stage_proposal(
        decisions=[StageDecision(decision="Keep the list", reason="It is the simplest fix.")],
        rejected=[
            StageRejection(
                alternative="A new class",
                evidence="src/devops_cli/roadmap/stage/stage_change.py:1866: the list already holds the data.",
            )
        ],
    )
    problems = content_problems(proposal)
    assert not any("A new class" in p or "Rejected alternatives" in p for p in problems)


def test_the_plan_that_adds_the_rule_gets_no_problem() -> None:
    proposal = make_stage_proposal(
        decisions=[
            StageDecision(
                decision="Put the rule in `_rejected_problems` beside `_security_problems` and call it from `content_problems`.",
                reason="The stage job and the replay both reach `content_problems` through `check_proposal`, so one rule set judges the job and the golden set.",
            )
        ],
        rejected=[
            StageRejection(
                alternative="Accept any non-empty sentence as the evidence of an alternative.",
                evidence="src/devops_cli/roadmap/stage/stage_change.py:2020: an opinion passes today and the defect of #3257 stays.",
            )
        ],
    )
    problems = content_problems(proposal)
    assert not any("Rejected alternatives" in p for p in problems)


def test_a_proposal_with_no_decision_and_no_alternative_gets_no_problem() -> None:
    proposal = make_stage_proposal(decisions=[], rejected=[])
    problems = content_problems(proposal)
    assert not any("Rejected alternatives" in p for p in problems)


def test_the_design_file_writes_the_alternative_under_rejected_alternatives() -> None:
    proposal = make_stage_proposal(
        decisions=[StageDecision(decision="Keep the list", reason="It is the simplest fix.")],
        rejected=[
            StageRejection(
                alternative="A new class",
                evidence="src/devops_cli/sample.py:42: the list holds the data.",
            )
        ],
    )
    files = render_change("sample", proposal, (), created=date(2026, 11, 23))
    design = files["openspec/changes/sample/design.md"]
    assert "## Rejected alternatives" in design
    assert "**A new class**: src/devops_cli/sample.py:42: the list holds the data." in design
