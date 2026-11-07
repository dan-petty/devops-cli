"""The decisions that the model proposes: the sources that support them, the marks refine writes
and the owner decisions it honours (#1335).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.roadmap.body_hash import extract_section_and_outside
from devops_cli.roadmap.refine.refine import (
    DesignOption,
    QuestionAnswer,
    RefinementProposal,
    inspect_checkout,
    needs_investigation,
    render_proposal_section,
    validate_proposal,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import READY, REPO, refine_round, seed_with_body

pytestmark = pytest.mark.usefixtures("keyring_store")


def _section_lines(store: InMemoryRoadmapStore, number: int) -> list[str]:
    _, section = extract_section_and_outside(store.read_issue_body(number))
    return (section or "").splitlines()


def test_a_mark_the_model_copies_is_replaced_by_the_one_the_answer_earns(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """An answer that holds an earlier round's mark gets one mark: "(best practice)" for a
    sourced decision, and "(proposed)" for an unsourced one, which the investigation then sees."""
    sha = inspect_checkout(git_repo, REPO)
    copied = [
        QuestionAnswer(
            question="Sourced?",
            answer="Use the library. (proposed)",
            kind="decision",
            sources=["src/sample.py"],
        ),
        QuestionAnswer(
            question="Unsourced?",
            answer="(proposed) Use Valkey. It is maintained.",
            kind="decision",
        ),
    ]
    proposal, open_qs = validate_proposal(
        READY.model_copy(update={"key_questions": copied}), "Body", set(), git_repo, sha, store
    )

    assert (
        [qa.answer for qa in proposal.key_questions],
        needs_investigation(proposal, open_qs),
    ) == (["Use the library. (best practice)", "Use Valkey. It is maintained. (proposed)"], True)


def test_only_an_answer_that_quotes_an_owner_decision_is_the_owners(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    sha = inspect_checkout(git_repo, REPO)
    body = "Body\n\n## Owner decisions\n- Use Valkey, not Redis.\n"
    answers = [
        QuestionAnswer(question="Cache?", answer="Redis", kind="decision"),
        QuestionAnswer(question="Store?", answer="Use Valkey, not Redis.", kind="decision"),
    ]
    proposal, _ = validate_proposal(
        READY.model_copy(update={"key_questions": answers}), body, set(), git_repo, sha, store
    )

    assert [qa.answer for qa in proposal.key_questions] == [
        "Redis (proposed)",
        "Use Valkey, not Redis. (owner decision)",
    ]


def test_the_investigation_hears_of_a_decision_whose_sources_failed(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A decision whose cited path the commit does not hold reaches the investigation as a
    decision with no verified source."""
    seed_with_body(store, "Body")
    answer = QuestionAnswer(
        question="Which parser?",
        answer="Use the library.",
        kind="decision",
        sources=["docs/parsers.md"],
    )
    model_fake.answer(READY.model_copy(update={"key_questions": [answer]}))

    refine_round(store, git_repo)

    assert json.loads(model_fake.calls[1].prompt)["open_questions"] == [
        "Which parser? (decision with no verified source)"
    ]


def test_a_url_source_renders_as_a_link_before_the_closing_bracket() -> None:
    url = "https://example.com/doc"
    answer = QuestionAnswer(question="Which?", answer="This.", kind="decision", sources=[url])
    section = render_proposal_section(
        READY.model_copy(update={"key_questions": [answer]}), [], "a" * 40, {url}
    )

    assert f"[sources: {url}]" in section


_LIBRARY = DesignOption(option="Use the library", chosen=True, reason="It is maintained.")


_PARSER = DesignOption(option="Write a parser", chosen=False, reason="It adds code to keep.")


def _decision(sources: list[str]) -> RefinementProposal:
    answer = QuestionAnswer(
        question="Which parser?",
        answer="Use the library.",
        kind="decision",
        sources=sources,
        options=[_LIBRARY, _PARSER],
    )
    return READY.model_copy(update={"key_questions": [answer]})


def test_a_sourced_decision_shows_its_options_and_the_best_practice_and_can_be_ready(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    number = seed_with_body(store, "Body")
    model_fake.answer(_decision(["src/sample.py"]))

    plan = refine_round(store, git_repo)

    lines = _section_lines(store, number)
    start = lines.index("### Key questions") + 1
    assert (plan.refined_items[0].next_step, model_fake.call_count, lines[start : start + 3]) == (
        "ready",
        1,
        [
            "- **Which parser?**: Use the library. (best practice) [sources: src/sample.py]",
            "  - Chosen: Use the library. It is maintained.",
            "  - Rejected: Write a parser. It adds code to keep.",
        ],
    )


def test_an_unsourced_decision_is_investigated_and_stays_proposed(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A decision with no source starts the investigation; when it finds none, the decision
    stays "(proposed)" and does not stop Ready."""
    number = seed_with_body(store, "Body")
    model_fake.answer(_decision([]))

    plan = refine_round(store, git_repo)

    lines = _section_lines(store, number)
    start = lines.index("### Key questions") + 1
    assert (plan.refined_items[0].next_step, model_fake.call_count, lines[start]) == (
        "ready",
        2,
        "- **Which parser?**: Use the library. (proposed)",
    )


def test_a_question_for_a_person_waits_on_a_person_with_no_investigation(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    seed_with_body(store, "Body")
    asked = QuestionAnswer(
        question="Which repository secret holds the key?",
        answer="Recommended: a new secret.",
        kind="person",
    )
    model_fake.answer(READY.model_copy(update={"key_questions": [asked]}))

    plan = refine_round(store, git_repo)

    refined = plan.refined_items[0]
    assert (refined.next_step, refined.step_details, model_fake.call_count) == (
        "person",
        ("Which repository secret holds the key? (a person decides)",),
        1,
    )
