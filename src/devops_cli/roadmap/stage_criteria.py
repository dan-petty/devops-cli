"""The acceptance criteria of an issue against the criteria list of a plan (#3019).

About 10 of 37 plans of 2026-11-01 dropped an acceptance criterion of the issue. The reply now
holds a `criteria` list: one entry for each criterion, with the group that delivers it or
`pending-person` and a reason. `criterion_problems` refuses a reply that leaves one out.

An acceptance criterion is a top-level item of a list under a heading named `Acceptance criteria`
in the part of the issue body that a person wrote. The block of the refine job
(`devops-roadmap-refine`) has its own `Acceptance criteria` heading in another form, so the check
cuts that block off first. A body with no such heading has no criterion, and nothing is missing.
A criterion is the source text of its item (code spans and links as written) with a task-list mark
and the whitespace around and inside it removed. An entry matches when its text is the same.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final, Literal, Self

from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict, model_validator

from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.lang import MESSAGES

PENDING_PERSON: Final[str] = "pending-person"
_HEADING_TITLE: Final[re.Pattern[str]] = re.compile(r"acceptance criteria:?", re.IGNORECASE)
_TASK_MARK: Final[re.Pattern[str]] = re.compile(r"^\[[ xX]\]\s+")
# A top-level list sits at nesting level 0, so its items are at level 1.
_ITEM_LEVEL: Final[int] = 1


class StageCriterion(BaseModel):
    """One acceptance criterion of the issue and who delivers it: the number of a group (from 1),
    or `pending-person`. A `pending-person` entry holds a reason."""

    model_config = ConfigDict(extra="forbid")

    criterion: str
    group: int | Literal["pending-person"]
    reason: str | None = None

    @model_validator(mode="after")
    def _pending_has_reason(self) -> Self:
        if isinstance(self.group, int) and self.group < 1:
            raise ValueError(MESSAGES.roadmap.stage_criterion_bad_group.format(group=self.group))
        if self.group == PENDING_PERSON and not (self.reason and self.reason.strip()):
            raise ValueError(
                MESSAGES.roadmap.stage_criterion_no_reason.format(criterion=self.criterion)
            )
        return self


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _without_refine_block(body: str) -> str:
    start = body.find(CONST_ROADMAP_REFINE_START_MARKER)
    if start < 0:
        return body
    end = body.find(CONST_ROADMAP_REFINE_END_MARKER, start)
    after = "" if end < 0 else body[end + len(CONST_ROADMAP_REFINE_END_MARKER) :]
    return f"{body[:start]}\n{after}"


def acceptance_criteria(body: str) -> list[str]:
    """The acceptance criteria of the issue body: the top-level list items under each heading
    `Acceptance criteria` of the part that a person wrote, each on one line, in order."""
    tokens = MarkdownIt("commonmark").parse(_without_refine_block(body))
    found: list[str] = []
    level = 0  # the level of the open `Acceptance criteria` heading, 0 when none is open
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            title = tokens[index + 1].content.strip()
            level = int(token.tag[1:]) if _HEADING_TITLE.fullmatch(title) else 0
        elif level and token.type == "list_item_open" and token.level == _ITEM_LEVEL:
            inline = next(t for t in tokens[index + 1 :] if t.type == "inline")
            text = _one_line(_TASK_MARK.sub("", inline.content.strip()))
            if text and text not in found:
                found.append(text)
    return found


def criterion_problems(
    criteria: Sequence[StageCriterion], issue_body: str, group_count: int
) -> list[str]:
    """One problem for each acceptance criterion of the issue that no entry of `criteria` holds,
    and for each entry that names a group the plan does not have. A problem quotes the exact text
    to copy."""
    texts = MESSAGES.roadmap
    mapped = {_one_line(entry.criterion) for entry in criteria}
    problems = [
        texts.stage_problem_criterion.format(criterion=criterion)
        for criterion in acceptance_criteria(issue_body)
        if criterion not in mapped
    ]
    problems.extend(
        texts.stage_problem_criterion_group.format(
            criterion=entry.criterion, group=entry.group, count=group_count
        )
        for entry in criteria
        if isinstance(entry.group, int) and entry.group > group_count
    )
    return problems
