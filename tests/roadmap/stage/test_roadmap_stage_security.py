"""`devops roadmap stage`: require a security section in design.md for sensitive plans (#3247)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.roadmap.stage.stage_change import (
    SECURITY_TRIGGER_PATHS,
    StageProposal,
    content_problems,
    render_change,
)
from tests.support.builders import make_stage_proposal


def test_a_plan_that_changes_security_md_with_no_security_text_is_refused() -> None:
    sample = make_stage_proposal()
    group = sample.groups[0].model_copy(
        update={
            "changes": ["SECURITY.md", "src/devops_cli/roadmap/stage/stage_change.py"],
            "creates": [],
            "creates_lines": {},
            "test": (
                "Write a test that builds the plan's own `StageProposal` and asserts that "
                "`content_problems` returns no problem for it, and that `src/devops_cli/sample.py` "
                "fails on the base"
            ),
        }
    )
    refused = make_stage_proposal(groups=[group], security="")
    problems = content_problems(refused)
    assert any("SECURITY.md" in p and "## Security" in p for p in problems)

    accepted = make_stage_proposal(
        groups=[group],
        security=(
            "Answers what crosses a trust boundary, what a person must confirm, and what test "
            "fails if the rule breaks."
        ),
    )
    assert content_problems(accepted) == []


def test_a_task_that_names_a_trigger_word_with_no_security_text_is_refused() -> None:
    sample = make_stage_proposal()
    group = sample.groups[0].model_copy(
        update={"implementation": "Store the credential in the keyring"}
    )
    refused = make_stage_proposal(groups=[group], security="")
    problems = content_problems(refused)
    assert any("credential" in p for p in problems)


def _plan_with_implementation(text: str) -> StageProposal:
    sample = make_stage_proposal()
    group = sample.groups[0].model_copy(update={"implementation": text})
    return make_stage_proposal(groups=[group], security="")


def test_a_trigger_word_inside_a_longer_word_needs_no_security_text() -> None:
    # `regression` holds `egress`; the live run of #4062 refused a test-only plan for it (#4254).
    proposal = _plan_with_implementation("Add a regression test for the logger bridge")
    assert content_problems(proposal) == []


def test_a_trigger_word_as_a_whole_word_or_in_a_phrase_is_refused() -> None:
    for text in (
        "Allow egress to the registry",
        "Change the egress policy of the pod",
        "Egress.",
        "Rename egress_policy",
    ):
        problems = content_problems(_plan_with_implementation(text))
        assert any("`egress`" in p for p in problems), text


def test_a_plural_trigger_word_matches() -> None:
    problems = content_problems(_plan_with_implementation("Rotate the stored credentials"))
    assert any("`credential`" in p for p in problems)


def test_a_trigger_phrase_of_two_words_matches_as_a_phrase() -> None:
    problems = content_problems(_plan_with_implementation("Add an admission policy for pods"))
    assert any("admission policy" in p for p in problems)


def test_a_plan_with_no_trigger_needs_no_security_text() -> None:
    proposal = make_stage_proposal(security="")
    assert content_problems(proposal) == []


def test_every_trigger_path_exists() -> None:
    for path_str in SECURITY_TRIGGER_PATHS:
        assert Path(path_str).exists(), f"Trigger path {path_str} does not exist"


def test_the_trigger_path_constant_is_documented() -> None:
    assert SECURITY_TRIGGER_PATHS.__doc__ is not None
    assert len(SECURITY_TRIGGER_PATHS.__doc__.strip()) > 0


def test_the_design_file_holds_the_security_section() -> None:
    security_text = "Answers trust boundary, human confirmation, and failure tests."
    proposal_with_security = make_stage_proposal(security=security_text)
    files_with = render_change(
        "sample-change",
        proposal_with_security,
        ["comment-thread"],
        created=date(2026, 11, 7),
    )
    design_with = files_with["openspec/changes/sample-change/design.md"]
    assert "## Security" in design_with
    assert security_text in design_with

    proposal_no_security = make_stage_proposal(security="")
    files_without = render_change(
        "sample-change",
        proposal_no_security,
        ["comment-thread"],
        created=date(2026, 11, 7),
    )
    design_without = files_without["openspec/changes/sample-change/design.md"]
    assert "## Security" not in design_without


def test_the_stage_prompt_names_the_security_rule() -> None:
    prompt = load_task_prompt("roadmap_stage_change.md")
    assert "`security`:" in prompt
    assert "## Security" in prompt
    assert "SECURITY.md" in prompt
    assert "credential" in prompt
