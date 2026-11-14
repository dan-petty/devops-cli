"""The owner-question form of the roadmap jobs (#3077).

A job that needs an owner decision guesses, or it stops with a comment that reads as a failure.
This module holds the one form that refine, stage and implement post: the question once, two or
three options with their results, a recommendation, the evidence and a hidden block with the
question hash.

The hash covers the question and the option texts, so two items that ask one question post one
frame: the older item holds it, and each other item gets a link to it. The recommendation and the
evidence are no part of the hash, since two items can give different reasons for one question.

The frame starts with the marker of the job that posts it, so the cap on the comments of that job
counts it and `comment_repeat` reads it as the job's own comment. The open frame is the marker of a
question that waits, so no status label is added (ADR 0016).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.roadmap.body_hash import hash_text
from devops_cli.roadmap.stores.store import IssueComment
from devops_cli.roadmap.trust import is_person_comment

# The text that opens the hidden block of a frame, and the block itself: a comment, so GitHub shows
# none of it, with the hash of the question and its option texts.
_FRAME_OPEN: Final[str] = "<!-- owner-question:"
_FRAME: Final[re.Pattern[str]] = re.compile(r"<!-- owner-question:(?P<hash>[0-9a-f]{64}) -->")


class QuestionOption(BaseModel):
    """One answer that the owner can give, and what the job does with it."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, description="The answer, as the owner gives it.")
    result: str = Field(min_length=1, description="What the job does with this answer.")


class OwnerQuestion(BaseModel):
    """One decision that only the owner can make, and the comment that asks it."""

    model_config = ConfigDict(frozen=True)

    marker: str = Field(min_length=1, description="The marker of the job that posts the comment.")
    question: str = Field(min_length=1, description="The decision that only the owner can make.")
    options: tuple[QuestionOption, ...] = Field(
        min_length=2,
        max_length=3,
        description="The two or three answers that the owner can give.",
    )
    recommendation: str = Field(min_length=1, description="The answer that the job recommends.")
    evidence: tuple[str, ...] = Field(
        min_length=1, description="The links that the owner reads before answering."
    )

    @property
    def hash(self) -> str:
        """The hash of the question and its option texts: two items that ask one question with
        the same options post one frame for it."""
        return hash_text("\n".join((self.question, *(option.text for option in self.options))))

    def render(self) -> str:
        """The comment of the frame: the marker of the job, the question once, each option with
        its result, the recommendation, the evidence and the hidden block with the hash."""
        options = "\n".join(
            f"{number}. {option.text}: {option.result}"
            for number, option in enumerate(self.options, start=1)
        )
        evidence = "\n".join(f"- {link}" for link in self.evidence)
        return (
            f"{self.marker}\n"
            f"**Owner question:** {self.question}\n\n"
            f"**Options**\n{options}\n\n"
            f"**Recommendation:** {self.recommendation}\n\n"
            f"**Evidence**\n{evidence}\n\n"
            f"{_FRAME_OPEN}{self.hash} -->"
        )

    def link_comment(self, *, frame_item: int, frame_url: str) -> str:
        """The comment of another item that asks the same question: a link to the frame that
        `frame_item` holds. It holds no hidden block, so only the frame answers the hash."""
        return (
            f"{self.marker}\n"
            f"The owner question of this item is on #{frame_item}: {frame_url}\n\n"
            "Answer it there."
        )


def frame_hash(body: str) -> str | None:
    """The hash of the hidden block of `body`, or None for a comment that holds no frame. A link
    comment holds none, so only the frame of a question answers its hash."""
    found = _FRAME.findall(body)
    return found[-1] if found else None


def answer_of(
    comments: Sequence[IssueComment], question_hash: str, *, actor: str | None = None
) -> IssueComment | None:
    """The newest reply to the frame of `question_hash` that a trusted person made, or None when
    the frame or the reply is absent. Only a comment after the frame counts, and only one that
    `is_person_comment` accepts: a reply of a stranger, of a bot or of `actor`, the account that
    the job acts as, is no answer."""
    frames = [
        index for index, comment in enumerate(comments) if frame_hash(comment.body) == question_hash
    ]
    if not frames:
        return None
    replies = [
        comment for comment in comments[frames[-1] + 1 :] if is_person_comment(comment, actor)
    ]
    return replies[-1] if replies else None
