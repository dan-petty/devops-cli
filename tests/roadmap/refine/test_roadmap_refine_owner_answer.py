"""The answer to an owner question resumes the items that the frame covers (#3077).

A reply of a trusted person to the frame of an owner question resumes every open item whose record
holds that question's hash: the request of each covered item carries the answer text and the
reference of the frame, and the record of each holds the answer. A reply of a stranger, of a bot or
of the account that the job acts as starts no run and records nothing, so the question stays open.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

import pytest

from devops_cli.roadmap.owner_question import frame_hash
from devops_cli.roadmap.refine.refine import (
    QuestionAnswer,
    RefinementProposal,
    RefinePlan,
    apply_refine,
    plan_refine,
)
from devops_cli.roadmap.stores.store import OwnerQuestionRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    READY,
    REPO,
    comment_bodies,
    require_item,
    seed_item,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

QUESTION = "Which store holds the record?"
OPEN_QUESTION = f"{QUESTION} (a person decides)"
ANSWER = "Use the roadmap store: it already holds the record of every job."
# The account that the job acts as: its own comment answers no question.
ACTOR = "devops-cli"
STRANGER = "Use a file in the checkout."
BOT = "Use the cluster."
JOB = "Use the job record."


def _question() -> RefinementProposal:
    """A proposal that leaves its one question to a person, so the round asks it."""
    return READY.model_copy(
        update={
            "key_questions": [
                QuestionAnswer(question=QUESTION, answer="A person picks it.", kind="person")
            ]
        }
    )


def _round(store: InMemoryRoadmapStore, source: Path, *, limit: int) -> RefinePlan:
    """One round of refine as the row of the Service runs it: it acts as `ACTOR`, whose own
    comments answer no question."""
    plan = plan_refine(store, repo=REPO, source=source, limit=limit, actor=ACTOR)
    apply_refine(store, plan)
    return plan


def test_a_trusted_answer_resumes_each_item_that_the_frame_covers(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The reply of a member to the frame of the older item resumes both items: each request
    carries the answer and the reference of the frame, and each record holds the answer."""
    store.seed_visibility(is_private=True)
    older = seed_item(store, "New", "P1-High")
    newer = seed_item(store, "New", "P1-High")
    model_fake.answer(_question(), _question(), READY)
    _round(store, git_repo, limit=2)
    asked = len(model_fake.calls)
    question_hash = require_item(store, older).job_record.get(OwnerQuestionRecordKey.HASH)
    store.seed_comment(older, ANSWER, author_association="MEMBER", author_login="alice")

    _round(store, git_repo, limit=2)

    requests = [json.loads(call.prompt) for call in model_fake.calls[asked:]]
    frame = require_item(store, older).url
    assert (
        [request["number"] for request in requests],
        [request["owner_answer"] for request in requests],
        [require_item(store, number).status for number in (older, newer)],
        [
            require_item(store, number).job_record.get(OwnerQuestionRecordKey.ANSWER)
            for number in (older, newer)
        ],
        [
            require_item(store, number).job_record.get(OwnerQuestionRecordKey.HASH)
            for number in (older, newer)
        ],
        frame_hash(comment_bodies(store, older)[0]),
    ) == (
        [older, newer],
        [{"question": OPEN_QUESTION, "answer": ANSWER, "frame": frame}] * 2,
        ["Ready", "Ready"],
        [ANSWER, ANSWER],
        [None, None],
        question_hash,
    )


def test_a_reply_of_a_stranger_a_bot_or_the_job_starts_no_run(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A reply of an account with no write access, of a bot and of the account that the job acts
    as answers no question: no request is sent, no answer is recorded, and the items keep waiting
    with the question open."""
    store.seed_visibility(is_private=True)
    older = seed_item(store, "New", "P1-High")
    newer = seed_item(store, "New", "P1-High")
    model_fake.answer(_question(), _question(), READY)
    _round(store, git_repo, limit=2)
    asked = len(model_fake.calls)
    question_hash = require_item(store, older).job_record.get(OwnerQuestionRecordKey.HASH)
    store.seed_comment(older, STRANGER, author_association="NONE", author_login="stranger")
    store.seed_comment(older, BOT, author_association="OWNER", author_login="helper[bot]")
    store.seed_comment(older, JOB, author_association="OWNER", author_login=ACTOR)

    plan = _round(store, git_repo, limit=2)

    assert (
        len(model_fake.calls) - asked,
        plan.refined_items,
        [require_item(store, number).status for number in (older, newer)],
        [
            require_item(store, number).job_record.get(OwnerQuestionRecordKey.ANSWER)
            for number in (older, newer)
        ],
        [
            require_item(store, number).job_record.get(OwnerQuestionRecordKey.HASH)
            for number in (older, newer)
        ],
        [len(comment_bodies(store, number)) for number in (older, newer)],
    ) == (0, [], ["New", "New"], [None, None], [question_hash, question_hash], [4, 1])
