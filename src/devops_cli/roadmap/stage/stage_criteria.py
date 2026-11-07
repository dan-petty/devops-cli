"""The requirement lines and acceptance criteria of an issue against the lists of a plan (#3019,
#3253).

About 10 of 37 plans of 2026-11-01 dropped an acceptance criterion of the issue. The reply now
holds a `criteria` list: one entry for each criterion, with the group that delivers it or
`pending-person` and a reason. `criterion_problems` refuses a reply that leaves one out.

A plan could also drop a requirement line that is no acceptance criterion: a named caller, a path,
a command or a design decision. `requirement_lines` gives each such line an ID in source order, and
the plan maps each ID to a group or to a stated reason.

An acceptance criterion is a top-level item of a list under a heading named `Acceptance criteria`
in the part of the issue body that a person wrote. The block of the refine job
(`devops-roadmap-refine`) has its own `Acceptance criteria` heading in another form, so the check
cuts that block off first. A body with no such heading has no criterion, and nothing is missing.
A criterion is the source text of its item (code spans and links as written) with a task-list mark
and the whitespace around and inside it removed. An entry matches when its text is the same.

A requirement line is a top-level bullet under a heading of the part that a person wrote, a
backticked repository path or `devops` command of its text, or a line that starts with `Decision:`.
The items of the acceptance-criteria list are left out, because `criteria` maps them. A bullet that
names a path or a command is one line of that kind, not two, and its text is the literal.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final, Literal, Self

from markdown_it import MarkdownIt
from markdown_it.token import Token
from pydantic import BaseModel, ConfigDict, model_validator

from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.lang import MESSAGES

PENDING_PERSON: Final[str] = "pending-person"
RequirementKind = Literal["command", "path", "decision", "bullet"]
_HEADING_TITLE: Final[re.Pattern[str]] = re.compile(r"acceptance criteria:?", re.IGNORECASE)
_TASK_MARK: Final[re.Pattern[str]] = re.compile(r"^\[[ xX]\]\s+")
# A top-level list sits at nesting level 0, so its items are at level 1.
_ITEM_LEVEL: Final[int] = 1
_DECISION_PREFIX: Final[str] = "Decision:"
# A `devops` command in a code span: the program, then each lowercase word of its name.
_COMMAND: Final[re.Pattern[str]] = re.compile(r"`(devops(?:\s+[a-z][a-z0-9-]*)+)`")
_CODE_SPAN: Final[re.Pattern[str]] = re.compile(r"`([^`\n]+)`")
# A word names a path when it ends in a dot and letters, as a root document such as SECURITY.md
# does. A version such as `v1.2` is no path.
_PATH_SUFFIX: Final[re.Pattern[str]] = re.compile(r"\.[A-Za-z]+$")
_REQUIREMENT_ID: Final[str] = "REQ-{number:03d}"


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


class RequirementLine(BaseModel):
    """One requirement line of the issue, with the ID that the plan maps: a bullet of a section
    that a person wrote, a backticked repository path or `devops` command of its text, or a
    `Decision:` line. `source_line` is the line of the body, from 1."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: RequirementKind
    text: str
    source_line: int


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _without_refine_block(body: str) -> str:
    start = body.find(CONST_ROADMAP_REFINE_START_MARKER)
    if start < 0:
        return body
    end = body.find(CONST_ROADMAP_REFINE_END_MARKER, start)
    after = "" if end < 0 else body[end + len(CONST_ROADMAP_REFINE_END_MARKER) :]
    return f"{body[:start]}\n{after}"


def _is_repository_path(word: str) -> bool:
    """Whether a code span names a repository path: it holds a slash, or it ends in a dot and
    letters, as the name of a root document does."""
    return " " not in word and ("/" in word or _PATH_SUFFIX.search(word) is not None)


def _requirement_of_text(text: str) -> tuple[RequirementKind, str] | None:
    """The kind and the text of a requirement line, or `None` for prose that names no
    requirement. A decision line keeps its text, and a command or a path gives the literal."""
    one = _one_line(text)
    if not one:
        return None
    if one.startswith(_DECISION_PREFIX):
        return "decision", one
    command = _COMMAND.search(one)
    if command is not None:
        return "command", command.group(1)
    for span in _CODE_SPAN.finditer(one):
        if _is_repository_path(span.group(1)):
            return "path", span.group(1)
    return None


def _item_requirement(text: str) -> tuple[RequirementKind, str]:
    """The kind and the text of a bullet: the literal it names, or its own text."""
    found = _requirement_of_text(text)
    return found if found is not None else ("bullet", text)


def _item_text(tokens: Sequence[Token], index: int) -> str:
    """The text of the list item at `index`, on one line, with no task-list mark."""
    for token in tokens[index + 1 :]:
        if token.type == "inline":
            return _one_line(_TASK_MARK.sub("", token.content.strip()))
        if token.type == "list_item_close" and token.level == tokens[index].level:
            break
    return ""


def _item_requirements(
    tokens: Sequence[Token], index: int
) -> list[tuple[int, RequirementKind, str]]:
    """The requirement line of the top-level list item at `index`, or no line for an empty one."""
    source = tokens[index].map
    text = _item_text(tokens, index)
    if source is None or not text:
        return []
    kind, value = _item_requirement(text)
    return [(source[0] + 1, kind, value)]


def _paragraph_requirements(token: Token) -> list[tuple[int, RequirementKind, str]]:
    """One requirement line for each line of a paragraph that names one."""
    if token.map is None:
        return []
    found: list[tuple[int, RequirementKind, str]] = []
    for offset, line in enumerate(token.content.split("\n")):
        requirement = _requirement_of_text(line)
        if requirement is not None:
            kind, text = requirement
            found.append((token.map[0] + offset + 1, kind, text))
    return found


def _acceptance_level(tokens: Sequence[Token], index: int) -> int:
    """The level of the `Acceptance criteria` heading at `index`, or 0 for another heading."""
    level = int(tokens[index].tag[1:])
    return level if _HEADING_TITLE.fullmatch(tokens[index + 1].content.strip()) else 0


def _is_top_paragraph(tokens: Sequence[Token], index: int) -> bool:
    """Whether the inline token at `index` is the text of a top-level paragraph, not of a heading
    or of a list item."""
    previous = tokens[index - 1] if index > 0 else None
    return previous is not None and previous.type == "paragraph_open" and previous.level == 0


def requirement_lines(body: str) -> list[RequirementLine]:
    """The requirement lines of the issue body, each with the ID `REQ-<number>` in source order:
    the top-level bullets under the headings of the part that a person wrote, the backticked
    repository paths and `devops` commands of its text, and each line that starts with
    `Decision:`. The items of the acceptance-criteria list are left out, and so is the block of
    the refine job."""
    tokens = MarkdownIt("commonmark").parse(_without_refine_block(body))
    found: list[tuple[int, RequirementKind, str]] = []
    acceptance_level = 0
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            acceptance_level = _acceptance_level(tokens, index)
        elif token.type == "list_item_open" and token.level == _ITEM_LEVEL:
            if not acceptance_level:
                found.extend(_item_requirements(tokens, index))
        elif token.type == "inline" and _is_top_paragraph(tokens, index):
            found.extend(_paragraph_requirements(token))
    found.sort(key=lambda entry: entry[0])
    return [
        RequirementLine(
            id=_REQUIREMENT_ID.format(number=number), kind=kind, text=text, source_line=line
        )
        for number, (line, kind, text) in enumerate(found, start=1)
    ]


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
