"""The owner-question form of the roadmap jobs (#3077).

A job that needs an owner decision posts one form: the question once, two or three options with
their results, a recommendation, the evidence and a hidden block with the question hash. The same
question and option texts give the same hash, so two items that ask one question post one frame
and the other items link it. A reply of a trusted person answers the frame; a reply of a stranger,
a bot or the account that the job acts as does not.

The tests import the module inside each test and helper, so this file collects on the base commit,
where the module does not exist, and each test fails on its own case.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.config.constants import CONST_ROADMAP_REFINE_COMMENT_MARKER
from devops_cli.roadmap.stores.store import IssueComment

NOW = datetime(2026, 11, 5, 12, tzinfo=UTC)
QUESTION = "Should the job split the group of the plan?"
RECOMMENDATION = "Split the group, because the plan reads one group at a time."
SPLIT_EVIDENCE = "https://example.com/issues/3077#issuecomment-1"
SPLIT = ("Split the group", "two plans of half the size")
KEEP = ("Keep the group", "one plan over the budget")
DEFER = ("Defer the group", "the item waits for another round")


def _question(
    *,
    options: tuple[tuple[str, str], ...] = (SPLIT, KEEP),
    recommendation: str = RECOMMENDATION,
    evidence: tuple[str, ...] = (SPLIT_EVIDENCE,),
) -> Any:
    """A question of the refine job with the given options, recommendation and evidence."""
    from devops_cli.roadmap.owner_question import OwnerQuestion, QuestionOption

    return OwnerQuestion(
        marker=CONST_ROADMAP_REFINE_COMMENT_MARKER,
        question=QUESTION,
        options=tuple(QuestionOption(text=text, result=result) for text, result in options),
        recommendation=recommendation,
        evidence=evidence,
    )


def _comment(body: str, login: str, association: str) -> IssueComment:
    return IssueComment(
        body=body, created_at=NOW, author_login=login, author_association=association
    )


def test_the_form_holds_the_question_once_with_its_options_and_the_hash() -> None:
    question = _question()

    rendered = question.render()

    assert (
        rendered.count(QUESTION),
        len(question.options),
        [text in rendered and result in rendered for text, result in (SPLIT, KEEP)],
        RECOMMENDATION in rendered,
        SPLIT_EVIDENCE in rendered,
        f"<!-- owner-question:{question.hash} -->" in rendered,
        rendered.startswith(CONST_ROADMAP_REFINE_COMMENT_MARKER),
    ) == (1, 2, [True, True], True, True, True, True)


def test_a_form_holds_three_options_and_refuses_one_option_or_four() -> None:
    rendered = _question(options=(SPLIT, KEEP, DEFER)).render()

    assert (DEFER[0] in rendered, DEFER[1] in rendered) == (True, True)
    with pytest.raises(ValidationError, match="at least 2 items"):
        _question(options=(SPLIT,))
    with pytest.raises(ValidationError, match="at most 3 items"):
        _question(options=(SPLIT, KEEP, DEFER, DEFER))


def test_the_same_question_and_options_give_the_same_hash() -> None:
    same = _question(recommendation="Keep the group.", evidence=("https://example.com/other",))
    other = _question(options=(KEEP, SPLIT))

    assert (
        _question().hash == same.hash,
        _question().hash == other.hash,
        len(_question().hash),
    ) == (True, False, 64)


def test_the_frame_hash_reads_the_hidden_block_and_a_link_holds_none() -> None:
    from devops_cli.roadmap.owner_question import frame_hash

    question = _question()

    assert (
        frame_hash(question.render()),
        frame_hash("A comment of the job that holds no question."),
        frame_hash(question.link_comment(frame_item=12, frame_url="https://example.com/issues/12")),
    ) == (question.hash, None, None)


def test_a_link_comment_names_the_item_that_holds_the_frame() -> None:
    link = _question().link_comment(
        frame_item=12, frame_url="https://example.com/issues/12#issuecomment-1"
    )

    assert (
        link.startswith(CONST_ROADMAP_REFINE_COMMENT_MARKER),
        "#12" in link,
        "https://example.com/issues/12#issuecomment-1" in link,
    ) == (True, True, True)


def test_the_answer_is_the_newest_trusted_reply_after_the_frame() -> None:
    from devops_cli.roadmap.owner_question import answer_of

    question = _question()
    frame = _comment(question.render(), "the-job", "CONTRIBUTOR")
    owner = _comment("Split the group.", "a-person", "OWNER")
    colleague = _comment("Keep the group.", "a-colleague", "MEMBER")
    stranger = _comment("I have a view too.", "a-stranger", "NONE")

    assert answer_of([frame, owner, stranger, colleague], question.hash) == colleague


def test_a_reply_of_a_stranger_or_a_bot_is_no_answer() -> None:
    from devops_cli.roadmap.owner_question import answer_of

    question = _question()
    frame = _comment(question.render(), "the-job", "CONTRIBUTOR")
    stranger = _comment("Split the group.", "a-stranger", "NONE")
    bot = _comment("Split the group.", "dependabot[bot]", "CONTRIBUTOR")

    assert (
        answer_of([frame, stranger, bot], question.hash),
        answer_of([stranger, bot], question.hash),
    ) == (None, None)


def test_a_reply_of_the_account_that_the_job_acts_as_is_no_answer() -> None:
    from devops_cli.roadmap.owner_question import answer_of

    question = _question()
    frame = _comment(question.render(), "the-job", "CONTRIBUTOR")
    own = _comment("Split the group.", "the-job", "OWNER")

    assert (
        answer_of([frame, own], question.hash, actor="the-job"),
        answer_of([frame, own], question.hash),
    ) == (None, own)
