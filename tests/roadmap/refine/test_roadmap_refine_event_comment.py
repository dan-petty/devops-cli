"""The comment of a refine round is the event of a change of its result (#6196).

The body section of refine holds the result: the design, the open questions, Fit, the suspected
block, the dependencies, the watched files and the new items of the deferred parts. The labels hold
the Status, and `checked-at` holds the commit. A comment names the next step and the parts of the
section that hold it. It holds no line of the section, no commit and no Status sentence. It posts
only when the next step or the section differs from the round before. A round that posts none
records the time of its read, and the wait starts there. The model still reads each reply since
refine's last comment, so no reply is lost.

The tests import the builders that the base tree lacks inside each test, so this file collects on
the base commit and each test fails on its own case.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest
import time_machine

from devops_cli.roadmap.body_hash import extract_section_and_outside
from devops_cli.roadmap.owner_question import frame_hash
from devops_cli.roadmap.refine import refine
from devops_cli.roadmap.refine.refine import (
    NextStep,
    RefinementProposal,
    apply_refine,
    next_step_of,
    owner_question_of,
    plan_refine,
    render_proposal_section,
    step_comment,
)
from devops_cli.roadmap.stores.store import (
    CloseReason,
    OwnerQuestionRecordKey,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    CITED_PATH,
    QUESTION,
    READY,
    REFINE_HEAD_SHA,
    REFINE_MARKER,
    REPO,
    SPLIT,
    block_in_code,
    comment_bodies,
    refine_round,
    replies_sent,
    require_item,
    seed_item,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

_OPEN_QUESTION = "Which store holds the record? (a person decides)"
_START = datetime(2026, 11, 17, 9, tzinfo=UTC)
# A line of the section that holds no content: a heading, a blank line or no value.
_NO_CONTENT = re.compile(r"^(?:#+ .*|None\.|)$")
_LIST_MARK = re.compile(r"^(?:[-*]|\d+\.)\s+")
_CHECKED_AT = re.compile(r"<!-- checked-at: sha=([0-9a-f]+) -->")


def _facts(section: str) -> list[str]:
    """The content of each line of `section` without its list mark: what a comment must not
    repeat. The `checked-at` line gives its commit, as the short form that a comment would name."""
    _, inside = extract_section_and_outside(section)
    assert inside is not None
    facts: list[str] = []
    for line in inside.splitlines():
        text = _LIST_MARK.sub("", line.strip())
        commit = _CHECKED_AT.fullmatch(text)
        if commit is not None:
            facts.append(commit.group(1)[:7])
        elif not _NO_CONTENT.fullmatch(text):
            facts.append(text)
    return facts


@dataclass(frozen=True)
class _Case:
    """One result of a round: the proposal, what validation left open and what the step
    reads."""

    proposal: RefinementProposal
    open_questions: tuple[str, ...] = ()
    block_paths: tuple[str, ...] = ()
    deferred: tuple[int, ...] = ()
    blockers: tuple[int, ...] = ()
    is_ready: bool = False
    waiting_for_alternatives: bool = False


_CASES = {
    "ready": _Case(READY, deferred=(21, 22), is_ready=True),
    "person": _Case(QUESTION, open_questions=(_OPEN_QUESTION,)),
    "suspected-block": _Case(block_in_code(None), block_paths=(CITED_PATH,)),
    "split": _Case(SPLIT),
    "blocked": _Case(block_in_code(12), block_paths=(CITED_PATH,), blockers=(12,)),
    "alternatives": _Case(READY, waiting_for_alternatives=True),
}


@pytest.mark.parametrize("case", _CASES.values(), ids=_CASES.keys())
def test_no_line_of_the_section_is_in_the_comment_of_the_same_result(
    store: InMemoryRoadmapStore, case: _Case
) -> None:
    """The real builders make the section and the comment of one result. The comment names the
    section, and it repeats no content line of the section, no commit and no Status sentence.
    The item is Ready, so a comment that tells of a Status change would show it."""
    item = require_item(store, seed_item(store, "Ready", "P1-High"))
    section = render_proposal_section(
        case.proposal,
        list(case.open_questions),
        REFINE_HEAD_SHA,
        set(),
        block_paths=case.block_paths,
        deferred=case.deferred,
    )
    step, details, _ = next_step_of(
        case.proposal,
        case.open_questions,
        case.blockers,
        is_ready=case.is_ready,
        waiting_for_alternatives=case.waiting_for_alternatives,
    )
    parts = refine.section_parts(
        step, case.open_questions, block_paths=case.block_paths, moved=bool(case.deferred)
    )

    comment = step_comment(item, step, details, parts=parts)

    assert (
        [fact for fact in _facts(section) if fact in comment],
        "Status" in comment,
        "Proposed design" in comment,
        [part in section for part in parts],
    ) == ([], False, True, [True] * len(parts))


def test_the_section_holds_the_watched_files_in_order_and_the_new_items_of_the_parts() -> None:
    """The files whose change ends a wait and the issues of the deferred parts are part of the
    result, so the section holds them, last. The files are sorted, so another order of the same
    files gives the same section."""
    proposal = block_in_code(None)

    sections = [
        render_proposal_section(
            proposal, [], REFINE_HEAD_SHA, set(), block_paths=paths, deferred=(21, 22)
        )
        for paths in (("src/b.py", CITED_PATH), (CITED_PATH, "src/b.py"))
    ]

    _, inside = extract_section_and_outside(sections[0])
    assert inside is not None
    assert (sections[0] == sections[1], inside.rstrip().splitlines()[-7:]) == (
        True,
        [
            "### Watched files",
            "A commit on the default branch that changes one of these files starts the next "
            "refine round.",
            "- `src/b.py`",
            "- `src/sample.py`",
            "",
            "### Moved to new items",
            "#21, #22",
        ],
    )


def test_a_round_whose_result_is_the_one_before_posts_no_comment_and_its_read_starts_the_wait(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A person replies, and the next round finds the same question: it posts no comment and
    records the time of its read. The round after it keeps the item waiting with no model call.
    A later reply ends the wait, and the model reads both replies since refine's last comment."""
    store.seed_visibility(is_private=True)
    model_fake.answer(QUESTION)
    with time_machine.travel(_START, tick=False) as clock:
        number = seed_item(store, "New", "P1-High")
        refine_round(store, git_repo)
        clock.shift(timedelta(minutes=5))
        store.as_actor("alice").comment(number, "The first reply.")
        clock.shift(timedelta(minutes=5))
        read_at = datetime.now(UTC)
        refine_round(store, git_repo)
        calls = model_fake.call_count
        clock.shift(timedelta(minutes=5))
        quiet = plan_refine(store, repo=REPO, source=git_repo)
        quiet_calls = model_fake.call_count - calls
        clock.shift(timedelta(minutes=5))
        store.as_actor("alice").comment(number, "The second reply.")
        clock.shift(timedelta(minutes=5))
        again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [body for body in comment_bodies(store, number) if REFINE_MARKER in body][1:],
        require_item(store, number).job_record.get(RefineRecordKey.REPEATED_AT),
        [(w.item.number, w.step) for w in quiet.waiting_items],
        quiet_calls,
        [r.item.number for r in again.refined_items],
        replies_sent(model_fake),
    ) == (
        [],
        read_at.isoformat(),
        [(number, NextStep.PERSON)],
        0,
        [number],
        ["The first reply.", "The second reply."],
    )


def test_a_reply_made_while_a_round_with_no_comment_runs_ends_the_wait(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A person replies after a round read the comments and before it wrote its result. The round
    finds the result of the round before, so it posts no comment and records the time of its read.
    The reply is newer than that time, so it ends the wait, and the model reads it."""
    store.seed_visibility(is_private=True)
    model_fake.answer(QUESTION)
    with time_machine.travel(_START, tick=False) as clock:
        number = seed_item(store, "New", "P1-High")
        refine_round(store, git_repo)
        clock.shift(timedelta(minutes=5))
        store.as_actor("alice").comment(number, "The first reply.")
        clock.shift(timedelta(minutes=5))
        read_at = datetime.now(UTC)
        plan = plan_refine(store, repo=REPO, source=git_repo)
        clock.shift(timedelta(minutes=1))
        store.as_actor("alice").comment(number, "The reply during the round.")
        clock.shift(timedelta(minutes=1))
        apply_refine(store, plan)
        clock.shift(timedelta(minutes=5))
        again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        require_item(store, number).job_record.get(RefineRecordKey.REPEATED_AT),
        [r.item.number for r in again.refined_items],
        replies_sent(model_fake),
    ) == (
        read_at.isoformat(),
        [number],
        ["The first reply.", "The reply during the round."],
    )


def test_a_round_whose_next_step_changes_posts_one_event_with_no_commit_and_no_status(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A reply answers the question, and the next round sets the item Ready: the step changed, so
    the round posts its event. The event names the section, and the labels and `checked-at` hold
    the Status and the commit."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(QUESTION, READY)
    refine_round(store, git_repo)
    store.as_actor("alice").comment(number, "The job record holds it.")

    refine_round(store, git_repo)

    ready = comment_bodies(store, number)[-1]
    assert (
        require_item(store, number).status,
        ready.startswith(REFINE_MARKER),
        "Proposed design" in ready,
        "Status" in ready,
        REFINE_HEAD_SHA[:7] in ready,
        require_item(store, number).job_record.get(RefineRecordKey.REPEATED_AT),
    ) == ("Ready", True, True, False, False, None)


def test_a_round_whose_section_changes_posts_the_event_again(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A reply, and the next round proposes another split: the step is the same, but the section
    changed, so the round posts its event again after the reply."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    other = SPLIT.model_copy(update={"split_offs": ["The first change.", "Another change."]})
    model_fake.answer(SPLIT, other)
    refine_round(store, git_repo)
    store.as_actor("alice").comment(number, "Split it in another way.")

    refine_round(store, git_repo)

    refine_comments = [body for body in comment_bodies(store, number) if REFINE_MARKER in body]
    _, section = extract_section_and_outside(store.read_issue_body(number))
    assert (len(refine_comments), "Another change." in (section or "")) == (2, True)


def test_the_frame_names_the_section_in_place_of_the_question_that_the_section_holds(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The open question is in the section. The frame names that place, and it keeps the hidden
    block of the hash of the question, which the record keeps."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(QUESTION)

    refine_round(store, git_repo)

    (frame,) = comment_bodies(store, number)
    _, section = extract_section_and_outside(store.read_issue_body(number))
    record = require_item(store, number).job_record
    assert (
        _OPEN_QUESTION in frame,
        f"- {_OPEN_QUESTION}" in (section or ""),
        "Open questions" in frame,
        frame_hash(frame),
        record.get(OwnerQuestionRecordKey.TEXT),
    ) == (False, True, True, record.get(OwnerQuestionRecordKey.HASH), _OPEN_QUESTION)


def test_the_frame_of_two_open_questions_names_the_first_one_that_it_asks(
    store: InMemoryRoadmapStore,
) -> None:
    """The section lists two open questions, and the frame asks the first one: its options, its
    answer and its hash cover that question alone. So the frame names the first point of Open
    questions, and a person knows which question it asks."""
    item = require_item(store, seed_item(store, "New", "P1-High"))
    questions = (_OPEN_QUESTION, "Which job reads the record? (a person decides)")
    step, details, _ = next_step_of(QUESTION, questions, (), is_ready=False)
    parts = refine.section_parts(step, questions, block_paths=(CITED_PATH,))
    question = owner_question_of(item, step, details)

    frame = step_comment(item, step, details, parts=parts)

    assert question is not None
    assert (
        frame.splitlines()[1],
        frame_hash(frame),
        question.question,
    ) == (
        "**Owner question:** See the first point of Open questions and Watched files in the "
        "section Proposed design of the body.",
        question.hash,
        _OPEN_QUESTION,
    )


def test_an_item_whose_frame_holder_closed_posts_the_frame_on_the_same_result(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The second item that asks a question holds a link to the frame of the older item. The older
    item closes, so no open item holds the frame. The next round of the second item finds the same
    result, and it posts the frame, so a person can answer the question."""
    store.seed_visibility(is_private=True)
    older = seed_item(store, "New", "P1-High")
    newer = seed_item(store, "New", "P1-High")
    model_fake.answer(QUESTION)
    refine_round(store, git_repo, limit=2)
    store.as_actor("alice").close_by_hand(older, CloseReason.COMPLETED)

    refine_round(store, git_repo)

    record = require_item(store, newer).job_record
    question_hash = record.get(OwnerQuestionRecordKey.HASH)
    assert (
        [frame_hash(body) for body in comment_bodies(store, newer)],
        question_hash is not None,
        record.get(RefineRecordKey.FRAME),
    ) == ([None, question_hash], True, str(newer))


def test_an_answer_on_the_frame_of_an_older_item_resumes_the_linked_item_once(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A member answers the frame that the older item holds, and both items look again with the
    answer. The question stays open, so neither round posts a comment. The answer is older than the
    round of each item, so the next round keeps both items waiting with no model call."""
    store.seed_visibility(is_private=True)
    model_fake.answer(QUESTION)
    with time_machine.travel(_START, tick=False) as clock:
        older = seed_item(store, "New", "P1-High")
        newer = seed_item(store, "New", "P1-High")
        refine_round(store, git_repo, limit=2)
        clock.shift(timedelta(minutes=5))
        store.seed_comment(
            older, "Keep it in the record.", author_association="MEMBER", author_login="alice"
        )
        clock.shift(timedelta(minutes=5))
        resumed = refine_round(store, git_repo, limit=2)
        calls = model_fake.call_count
        clock.shift(timedelta(minutes=5))
        quiet = plan_refine(store, repo=REPO, source=git_repo, limit=2)

    assert (
        sorted(r.item.number for r in resumed.refined_items),
        [len(comment_bodies(store, number)) for number in (older, newer)],
        sorted(w.item.number for w in quiet.waiting_items),
        model_fake.call_count - calls,
    ) == ([older, newer], [2, 1], [older, newer], 0)
