"""The proposal that the model returns to refine: its sources, its key questions, its criteria, its
size and the design section that refine renders from it (#1335).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass
import json

import pytest
from pydantic import ValidationError

from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import CONST_ROADMAP_REFINE_CONTEXT_MAX_TOKENS
from devops_cli.roadmap.body_hash import extract_section_and_outside
from devops_cli.roadmap.refine.refine import (
    AcceptanceCriterion,
    DeferredPart,
    DesignOption,
    QuestionAnswer,
    RefinementProposal,
    apply_refine,
    check_ready,
    inspect_checkout,
    plan_refine,
    render_proposal_section,
    validate_proposal,
)
from devops_cli.roadmap.stores.store import (
    ItemField,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    CRITERION,
    CRITERION_JSON,
    NO_OPEN_TOOL,
    PLACED,
    REPO,
    MockLLMClient,
    require_item,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_validate_proposal_sources_and_questions(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    sha = inspect_checkout(git_repo, REPO)
    body = (
        "## Description\nSome description.\n\n"
        "## Key questions\n- How to authenticate?\n- What database is used?\n\n"
        "## Owner decisions\n- Use SQLite for local storage\n"
    )
    raw = RefinementProposal(
        existing_tool=NO_OPEN_TOOL,
        problem_statement="Problem statement",
        acceptance_criteria=[CRITERION],
        key_questions=[
            # Fact with valid file source
            QuestionAnswer(
                question="How to authenticate?",
                answer="Token based",
                kind="fact",
                sources=["src/sample.py:1"],
                body_question=1,
            ),
            # Fact with invalid source
            QuestionAnswer(
                question="What is the port?",
                answer="Port 8080",
                kind="fact",
                sources=["src/nonexistent.py:99"],
            ),
            # Decision quoting owner decision
            QuestionAnswer(
                question="Which database?",
                answer="Use SQLite for local storage",
                kind="decision",
                sources=[],
            ),
            # Decision not quoting owner decision
            QuestionAnswer(
                question="Which framework?",
                answer="Use Typer",
                kind="decision",
                sources=[],
            ),
        ],
        fits_one_pr=True,
    )

    validated, open_qs = validate_proposal(
        raw, body, {"https://example.com/doc"}, git_repo, sha, store
    )
    answers = {qa.question: qa.answer for qa in validated.key_questions}

    assert (
        "(owner decision)" in answers["Which database?"],
        "(proposed)" in answers["Which framework?"],
        any("What database is used?" in q for q in open_qs),
        any("What is the port?" in q for q in open_qs),
    ) == (True, True, True, True)


@pytest.mark.parametrize(
    "answered",
    [[], [QuestionAnswer(question="Which store?", answer="The job record.", kind="decision")]],
    ids=["none", "answered"],
)
def test_the_key_questions_of_refines_own_section_are_never_asked_again(
    git_repo: Path, store: InMemoryRoadmapStore, answered: list[QuestionAnswer]
) -> None:
    """Refine reads the person's key questions from the body outside its own section, so the
    questions and the "None." its last section lists open no question when it refines the item
    again (#1758)."""
    sha = inspect_checkout(git_repo, REPO)
    proposal = RefinementProposal(
        existing_tool=NO_OPEN_TOOL,
        problem_statement="The item needs a design.",
        acceptance_criteria=[CRITERION],
    )
    last_round = proposal.model_copy(update={"key_questions": answered})
    body = f"Body\n\n{render_proposal_section(last_round, [], sha, set())}"

    assert validate_proposal(proposal, body, set(), git_repo, sha, store)[1] == []


def test_check_ready_matrix() -> None:
    base = RefinementProposal(
        existing_tool=NO_OPEN_TOOL,
        problem_statement="Problem exists",
        acceptance_criteria=[CRITERION],
        key_questions=[],
        fits_one_pr=True,
        suspected_block=None,
    )
    assert (
        check_ready(base, [], (), cycle=None),
        check_ready(base, ["Unresolved question"], (), cycle=None),
        check_ready(base, [], (7,), cycle=None),
        check_ready(base.model_copy(update={"fits_one_pr": False}), [], (), cycle=None),
        check_ready(
            base.model_copy(update={"suspected_block": "Waiting on auth"}), [], (), cycle=None
        ),
        check_ready(base.model_copy(update={"acceptance_criteria": []}), [], (), cycle=None),
        check_ready(base.model_copy(update={"problem_statement": ""}), [], (), cycle=None),
        check_ready(base.model_copy(update={"existing_tool": " "}), [], (), cycle=None),
        check_ready(
            base.model_copy(
                update={"acceptance_criteria": [CRITERION.model_copy(update={"then": ""})]}
            ),
            [],
            (),
            cycle=None,
        ),
        check_ready(base, [], (), cycle=(1, 2, 1)),
    ) == (True, False, False, False, False, False, False, False, False, False)


def test_a_criterion_takes_the_parts_of_an_openspec_requirement_and_refuses_the_old_keys() -> None:
    """A criterion is a requirement with a name, its SHALL or MUST text, a scenario name, WHEN
    and THEN; `description` and `verification` and a requirement without the keyword fail, and so
    does a reply with no existing-tool answer (#1849)."""
    with pytest.raises(ValidationError) as old_keys:
        AcceptanceCriterion.model_validate(
            {**CRITERION_JSON, "description": "It is designed.", "verification": "pytest"}
        )
    with pytest.raises(ValidationError) as no_keyword:
        AcceptanceCriterion.model_validate(
            {**CRITERION_JSON, "requirement": "The item has a design."}
        )
    with pytest.raises(ValidationError) as no_tool:
        RefinementProposal.model_validate({"problem_statement": "The item needs a design."})
    keyword = AcceptanceCriterion.model_validate(
        {**CRITERION_JSON, "requirement": "The tuner MUST read the ledger."}
    )
    assert (
        AcceptanceCriterion.model_validate(CRITERION_JSON) == CRITERION,
        keyword.requirement,
        [(error["type"], error["loc"]) for error in old_keys.value.errors()],
        [error["loc"] for error in no_keyword.value.errors()],
        all(word in str(no_keyword.value) for word in ("SHALL", "MUST")),
        [(error["type"], error["loc"]) for error in no_tool.value.errors()],
    ) == (
        True,
        "The tuner MUST read the ledger.",
        [("extra_forbidden", ("description",)), ("extra_forbidden", ("verification",))],
        [("requirement",)],
        True,
        [("missing", ("existing_tool",))],
    )


def test_the_proposed_design_renders_each_criterion_as_an_openspec_requirement_block() -> None:
    """Each criterion renders as `### Requirement:`, its text, `#### Scenario:` and the WHEN and
    THEN lines, and the existing-tool answer under its own heading (#1849)."""
    proposal = RefinementProposal(
        problem_statement="The tuner probes a backend that the ledger knows.",
        acceptance_criteria=[
            AcceptanceCriterion(
                name="Token cost",
                requirement="The tuner SHALL read the token cost from the ledger.",
                scenario="The ledger has the backend",
                when="the ledger holds records for the backend",
                then="the tuner sends no probe",
            )
        ],
        existing_tool="Renovate covers the pin.",
    )
    lines = render_proposal_section(proposal, [], "abc123", set()).splitlines()
    block = lines[lines.index("### Requirement: Token cost") :][:7]
    tool = lines.index("### Existing Tool Considered")
    assert (
        block,
        lines[tool + 1],
        [line for line in lines if line.startswith(("- Criterion", "  Verification:"))],
    ) == (
        [
            "### Requirement: Token cost",
            "The tuner SHALL read the token cost from the ledger.",
            "",
            "#### Scenario: The ledger has the backend",
            "- **WHEN** the ledger holds records for the backend",
            "- **THEN** the tuner sends no probe",
            "",
        ],
        "Renovate covers the pin.",
        [],
    )


def test_refining_twice_with_a_body_edit_between_leaves_only_the_second_section(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """A person's edit between two refines gets the section replaced, not a second one (#1470)."""
    num = store.seed_issue("Item", body="## Problem\nNeeds a design.", fields=PLACED)
    store.set_field(require_item(store, num), ItemField.STATUS, "New")

    def _refine(statement: str) -> None:
        # A suspected block keeps the item New, so the second run selects it again.
        proposal = RefinementProposal(
            existing_tool=NO_OPEN_TOOL,
            problem_statement=statement,
            acceptance_criteria=[CRITERION],
            suspected_block="Waiting",
        )
        plan = plan_refine(
            store,
            repo=REPO,
            source=git_repo,
            item_number=num,
            model=MockLLMClient(proposal=proposal),
        )
        apply_refine(store, plan)

    _refine("First design")
    edited = store.read_issue_body(num).replace(
        "Needs a design.", "Needs a design, see src/sample.py:1."
    )
    store.write_issue_body(num, edited)
    _refine("Second design")

    body = store.read_issue_body(num)
    outside, inside = extract_section_and_outside(body)
    assert (
        body.count("## Proposed design"),
        outside.strip(),
        inside is not None and "Second design" in inside,
    ) == (1, "## Problem\nNeeds a design, see src/sample.py:1.", True)


def test_refines_prompts_load_and_the_reply_prompt_names_every_field() -> None:
    """Verify the step prompts load and each asks the existing-tool question, and the reply
    prompt that both steps send names every key the schema allows, at the top level and in a
    criterion, a key question and an option, and no criterion key of the old shape (#1849)."""
    steps = [
        load_task_prompt(name)
        for name in ("roadmap_refine_proposal.md", "roadmap_refine_investigation.md")
    ]
    reply = load_task_prompt("roadmap_refine_reply.md")
    keys = [
        *RefinementProposal.model_fields,
        *AcceptanceCriterion.model_fields,
        *QuestionAnswer.model_fields,
        *DesignOption.model_fields,
        *DeferredPart.model_fields,
    ]
    assert (
        all(steps),
        [key for key in keys if f"`{key}`" not in reply],
        ["`existing_tool`" in step for step in steps],
        [old for old in ("`description`", "`verification`") if old in reply],
    ) == (True, [], [True, True], [])


def test_the_reply_prompt_asks_a_config_criterion_for_a_command_proof_as_the_stage_does() -> None:
    """Refine wrote criteria such as "A test evaluates the package rules of
    `.github/renovate.json`", and the stage planned a test that asserts a value of the file
    (#6080). The criterion of a manifest, a workflow or a config file names the command that
    proves it, with the phrase of the stage prompt."""
    phrase = "names a validator command or a live check as its proof"

    assert [
        phrase in load_task_prompt(name)
        for name in ("roadmap_refine_reply.md", "roadmap_stage_change.md")
    ] == [True, True]


def test_the_reply_prompt_limits_person_questions_to_owner_only_decisions() -> None:
    """The refine reply prompt reserves person questions for owner-only acts (`a merge, a secret,
    a repository setting or a host`), not review verdicts or milestones (#7040)."""
    reply = load_task_prompt("roadmap_refine_reply.md")

    assert (
        "a merge, a secret, a repository setting or a host" in reply,
        "a review verdict" in reply,
        "a milestone" in reply,
    ) == (True, False, False)


def test_refine_proposal_caps_context_at_job_constant(
    git_repo: Path, store: InMemoryRoadmapStore, config: Any
) -> None:
    """With an analysis window of 256,000, proposal context for an item citing a file of 60k
    tokens holds at most CONST_ROADMAP_REFINE_CONTEXT_MAX_TOKENS tokens (#5464)."""
    config(ai={"tasks": {"analysis": {"context_window": 256_000}}})
    large_file = git_repo / "src" / "large.py"
    large_file.write_text("# large file\n" + ("x = 1\n" * 30_000), encoding="utf-8")

    inspect_checkout(git_repo, REPO)
    body = "Review src/large.py:1-30000 now."
    number = store.seed_issue("Item with large context", body=body, fields=PLACED)
    person = store.as_actor("alice")
    person.set_field(require_item(person, number), ItemField.STATUS, "New")

    client = MockLLMClient()
    plan_refine(
        store,
        repo=REPO,
        source=git_repo,
        item_number=number,
        model=client,
    )
    assert len(client.calls) == 1
    req = json.loads(client.calls[0][1])
    ctx = req["context"]
    assert count_tokens(ctx) <= CONST_ROADMAP_REFINE_CONTEXT_MAX_TOKENS
