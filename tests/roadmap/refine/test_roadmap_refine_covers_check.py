"""The check that an item has an open tool that covers it: the question it asks, the reply that
closes it and the record it keeps (#1335).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config import constants
from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.roadmap.refine.refine import (
    QuestionAnswer,
    RefinementProposal,
    apply_refine,
    plan_refine,
)
from devops_cli.roadmap.stores.store import (
    AlternativesRecordKey,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    QUESTION,
    READY,
    REPO,
    comment_bodies,
    refine_round,
    replies_sent,
    require_item,
    seed_item,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


# ── The recorded check of the alternatives job (#2652) ────────────────────────

_SCANNER = "https://github.com/example/scanner"


_OTHER_SCANNER = "https://github.com/example/other-scanner"


_LACKS = "No SARIF output."


def _record_check(
    store: InMemoryRoadmapStore,
    number: int,
    verdict: str,
    *,
    tool: str | None = _SCANNER,
    comment: bool = True,
) -> None:
    """What the alternatives job leaves on item `number`: its block in the body, its keys in the
    job record, and its comment, unless `comment` is false (a comment that failed or was deleted)."""
    body = store.read_issue_body(number)
    block = (
        f"{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\n"
        f"Alternatives check of 2026-10-29: {verdict}.\n"
        f"{CONST_ROADMAP_ALTERNATIVES_END_MARKER}"
    )
    # A new check replaces the block of the last one, where it stands.
    if CONST_ROADMAP_ALTERNATIVES_START_MARKER in body:
        start = body.index(CONST_ROADMAP_ALTERNATIVES_START_MARKER)
        end = body.index(CONST_ROADMAP_ALTERNATIVES_END_MARKER) + len(
            CONST_ROADMAP_ALTERNATIVES_END_MARKER
        )
        store.write_issue_body(number, f"{body[:start]}{block}{body[end:]}")
    else:
        store.write_issue_body(number, f"{body}\n\n{block}")
    store.set_marks(
        require_item(store, number),
        {
            AlternativesRecordKey.CHECKED_AT: datetime.now(UTC).isoformat(),
            AlternativesRecordKey.VERDICT: verdict,
            AlternativesRecordKey.TOOL: tool,
        },
    )
    if comment:
        store.comment(
            number,
            f"{CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER}\n## Alternatives check: {verdict}\n"
            f"\nLacks:\n- {_LACKS}",
        )


def _alternatives_sent(model_fake: ModelFake) -> Any:
    """The `alternatives` key of the last proposal request."""
    return json.loads(model_fake.calls[-1].prompt)["alternatives"]


def _adopt_or_keep(question: str) -> QuestionAnswer:
    """A decision, with a source, that answers the body question numbered 1."""
    return QuestionAnswer(
        question=question,
        answer="Keep the item: the tool lacks SARIF output.",
        kind="decision",
        sources=["src/sample.py:1"],
        body_question=1,
    )


def _with_questions(*answers: QuestionAnswer) -> RefinementProposal:
    return READY.model_copy(update={"key_questions": list(answers)})


def test_an_item_with_a_block_reads_as_unchanged_after_a_round(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """Refine records the hash of the body without the job's block, the hash that the check for
    an unchanged item computes: an item with a block waits on its next step, and the model is
    not called again."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    _record_check(store, number, "none", tool=None)
    model_fake.answer(QUESTION)
    refine_round(store, git_repo)
    calls = model_fake.call_count

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        again.refined_items,
        [(w.item.number, w.step.value) for w in again.waiting_items],
        model_fake.call_count - calls,
    ) == ([], [(number, "person")], 0)


def test_a_block_that_the_job_writes_during_a_round_is_kept(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(READY)
    plan = plan_refine(store, repo=REPO, source=git_repo)

    _record_check(store, number, "none", tool=None)
    applied = apply_refine(store, plan)

    body = store.read_issue_body(number)
    assert (
        applied.refined_count,
        CONST_ROADMAP_ALTERNATIVES_START_MARKER in body,
        CONST_ROADMAP_REFINE_START_MARKER in body,
    ) == (0, True, False)


@pytest.mark.parametrize("verdict", ["partly", "none", "covers"])
def test_the_request_holds_the_recorded_check_and_the_jobs_comment_is_no_reply(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, verdict: str
) -> None:
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    _record_check(store, number, verdict, tool=None if verdict == "none" else _SCANNER)
    model_fake.answer(READY)

    plan_refine(store, repo=REPO, source=git_repo)

    sent = _alternatives_sent(model_fake)
    assert (
        sent["verdict"],
        sent["tool"],
        f"Alternatives check of 2026-10-29: {verdict}." in sent["block"],
        _LACKS in sent["comment"],
        replies_sent(model_fake),
    ) == (verdict, None if verdict == "none" else _SCANNER, True, True, [])


def test_the_request_holds_no_check_for_an_item_without_a_block_or_with_a_deleted_one(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    unchecked = seed_item(store, "New", "P1-High")
    deleted = seed_item(store, "New", "P2-Medium")
    _record_check(store, deleted, "covers")
    store.write_issue_body(deleted, "Body P2-Medium")
    model_fake.answer(READY)

    plan_refine(store, repo=REPO, source=git_repo, item_number=unchecked)
    first = _alternatives_sent(model_fake)
    plan_refine(store, repo=REPO, source=git_repo, item_number=deleted)

    assert (first, _alternatives_sent(model_fake)) == (None, None)


def test_the_prompts_tell_the_model_what_the_alternatives_key_holds() -> None:
    texts = [
        load_task_prompt("roadmap_refine_proposal.md"),
        load_task_prompt("roadmap_refine_investigation.md"),
    ]
    assert [("`alternatives`" in text, "Existing Tool Considered" in text) for text in texts] == [
        (True, True),
        (True, True),
    ]


def test_a_covers_check_with_no_reply_is_a_question_for_a_person_the_model_cannot_answer(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The item is otherwise ready, and the model answers the question as a decision: the
    question is still open, the next step is a person, and the item stays New."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    _record_check(store, number, "covers")
    model_fake.answer(_with_questions(_adopt_or_keep("Adopt the tool?")))

    plan = refine_round(store, git_repo)

    refined = plan.refined_items[0]
    assert (
        refined.next_step.value,
        refined.is_ready,
        len(refined.open_questions),
        _SCANNER.split("//")[1] in refined.open_questions[0],
        "adopt the tool" in refined.open_questions[0].lower(),
        refined.open_questions[0].endswith("(a person decides)"),
        require_item(store, number).status,
        "adopt the tool" in comment_bodies(store, number)[-1].lower(),
    ) == ("person", False, 1, True, True, True, "New", True)


def test_a_reply_and_an_answer_close_the_covers_question_and_set_the_item_ready(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    _record_check(store, number, "covers")
    model_fake.answer(READY)
    refine_round(store, git_repo)
    store.as_actor("alice").comment(number, "Keep it: the tool has no SARIF output.")
    model_fake.answer(_with_questions(_adopt_or_keep("Adopt the tool?")))

    plan = refine_round(store, git_repo)

    sent = json.loads(model_fake.calls[-1].prompt)
    assert (
        [q["number"] for q in sent["body_questions"]],
        sent["replies"],
        [(r.next_step.value, r.open_questions) for r in plan.refined_items],
        require_item(store, number).status,
    ) == ([1], ["Keep it: the tool has no SARIF output."], [("ready", [])], "Ready")


@pytest.mark.parametrize(
    "answers",
    [
        pytest.param([], id="no-answer"),
        pytest.param(
            [_adopt_or_keep("Adopt the tool?").model_copy(update={"kind": "person"})],
            id="a-person-answer",
        ),
    ],
)
def test_a_reply_without_an_answer_to_the_covers_question_leaves_it_open(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, answers: list[Any]
) -> None:
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    _record_check(store, number, "covers")
    model_fake.answer(READY)
    refine_round(store, git_repo)
    store.as_actor("alice").comment(number, "Let me think about it.")
    model_fake.answer(_with_questions(*answers))

    plan = refine_round(store, git_repo)

    refined = plan.refined_items[0]
    assert (refined.next_step.value, len(refined.open_questions), refined.is_ready) == (
        "person",
        1,
        False,
    )


def test_a_reply_answers_the_covers_question_when_the_jobs_comment_is_missing(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The job writes its comment last: a failed or deleted comment leaves the record and the
    block, and every comment of a person follows the check."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    _record_check(store, number, "covers", comment=False)
    store.as_actor("alice").comment(number, "Keep it: the tool has no SARIF output.")
    model_fake.answer(_with_questions(_adopt_or_keep("Adopt the tool?")))

    plan = refine_round(store, git_repo)

    sent = json.loads(model_fake.calls[-1].prompt)
    assert (
        [q["number"] for q in sent["body_questions"]],
        sent["alternatives"]["answers"],
        [(r.next_step.value, r.open_questions) for r in plan.refined_items],
    ) == ([1], ["Keep it: the tool has no SARIF output."], [("ready", [])])


def test_the_model_reads_the_answer_to_the_covers_question_after_refine_commented_again(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """Refine comments between the answer and a later round: the answer is no more in `replies`,
    so the request carries it in `alternatives.answers` and the round can close the question."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    _record_check(store, number, "covers")
    store.as_actor("alice").comment(number, "Keep it: the tool has no SARIF output.")
    model_fake.answer(_with_questions())
    refine_round(store, git_repo)
    store.as_actor("bob").comment(number, "Thanks, I read the plan.")
    model_fake.answer(_with_questions(_adopt_or_keep("Adopt the tool?")))

    plan = refine_round(store, git_repo)

    sent = json.loads(model_fake.calls[-1].prompt)
    assert (
        sent["replies"],
        sent["alternatives"]["answers"],
        [(r.next_step.value, r.open_questions) for r in plan.refined_items],
    ) == (
        ["Thanks, I read the plan."],
        ["Keep it: the tool has no SARIF output.", "Thanks, I read the plan."],
        [("ready", [])],
    )


@pytest.mark.parametrize(
    "marker",
    [
        constants.CONST_ROADMAP_STAGE_COMMENT_MARKER,
        constants.CONST_ROADMAP_INTAKE_REASON_MARKER,
    ],
)
def test_a_comment_of_another_job_is_no_answer_to_the_covers_question(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, marker: str
) -> None:
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    _record_check(store, number, "covers")
    store.comment(number, f"{marker}\nA job wrote this.")
    model_fake.answer(_with_questions(_adopt_or_keep("Adopt the tool?")))

    plan = refine_round(store, git_repo)

    sent = json.loads(model_fake.calls[-1].prompt)
    assert (
        sent["replies"],
        sent["alternatives"]["answers"],
        [(r.next_step.value, len(r.open_questions)) for r in plan.refined_items],
    ) == ([], [], [("person", 1)])


@pytest.mark.parametrize("verdict", ["partly", "none", "rejected", "in-use"])
def test_a_check_that_covers_nothing_whole_adds_no_question_and_leaves_the_ready_check_alone(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, verdict: str
) -> None:
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    _record_check(store, number, verdict, tool=None if verdict == "none" else _SCANNER)
    model_fake.answer(READY)

    plan = refine_round(store, git_repo)

    assert (
        [(r.next_step.value, r.open_questions) for r in plan.refined_items],
        require_item(store, number).status,
    ) == ([("ready", [])], "Ready")


def _asked(store: InMemoryRoadmapStore, number: int) -> str | None:
    return require_item(store, number).job_record.get(RefineRecordKey.ALTERNATIVES_ASKED)


def test_a_ready_item_that_gets_a_covers_check_goes_back_to_new_with_the_question(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    number = seed_item(store, "Ready", "P1-High", refined=True)
    quiet = plan_refine(store, repo=REPO, source=git_repo)
    _record_check(store, number, "covers")
    model_fake.answer(READY)

    plan = refine_round(store, git_repo)

    assert (
        quiet.refined_items,
        [(r.item.number, r.next_step.value) for r in plan.refined_items],
        require_item(store, number).status,
        _asked(store, number),
    ) == ([], [(number, "person")], "New", _SCANNER)


def test_the_same_covering_tool_found_again_asks_nothing_and_a_new_tool_asks_again(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    ready = seed_item(store, "Ready", "P1-High", refined=True)
    waiting = seed_item(store, "New", "P1-High")
    _record_check(store, ready, "covers")
    _record_check(store, waiting, "covers")
    model_fake.answer(READY)
    refine_round(store, git_repo)
    store.as_actor("alice").comment(ready, "Keep it: the tool has no SARIF output.")
    model_fake.answer(_with_questions(_adopt_or_keep("Adopt the tool?")))
    refine_round(store, git_repo)
    calls = model_fake.call_count

    _record_check(store, ready, "covers")
    _record_check(store, waiting, "covers")
    same = plan_refine(store, repo=REPO, source=git_repo)
    same_calls = model_fake.call_count - calls
    _record_check(store, waiting, "covers", tool=_OTHER_SCANNER)
    new = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        same.refined_items,
        [(w.item.number, w.step.value) for w in same.waiting_items],
        same_calls,
        [(r.item.number) for r in new.refined_items],
    ) == ([], [(waiting, "person")], 0, [waiting])


def test_a_check_that_no_longer_covers_clears_the_tool_refine_asked_about(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    _record_check(store, number, "covers")
    model_fake.answer(READY)
    refine_round(store, git_repo)
    asked = _asked(store, number)
    store.as_actor("alice").comment(number, "Checked again, please.")
    _record_check(store, number, "none", tool=None)

    refine_round(store, git_repo)

    assert (asked, _asked(store, number)) == (_SCANNER, None)
