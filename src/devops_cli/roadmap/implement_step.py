"""`devops roadmap implement` (#2664): one task group of a staged change, run in one bounded
context.

A change is `openspec/changes/<issue>-<slug>/` in a checkout, and its `tasks.md` holds numbered
groups (`## <n>. <title>`). A step reads one group and builds the inputs the model gets: the
item's title, problem and acceptance criteria, the change's `proposal.md`, `design.md` and
`tasks.md`, the group, and the files the group names, packed. It counts their tokens before the
first request and refuses a step that does not fit the window of `ai.tasks.implement`.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from markdown_it import MarkdownIt
from markdown_it.token import Token

from devops_cli.ai.context_budget import count_tokens, truncate_to_token_limit
from devops_cli.ai.context_packer import ContextPacker, PackingConfig
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_IMPLEMENT_CRITERIA_HEADINGS,
    CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS,
    CONST_ROADMAP_IMPLEMENT_PROBLEM_HEADINGS,
    CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS,
)
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.lang import MESSAGES

if TYPE_CHECKING:
    from devops_cli.roadmap.store import Item, RoadmapStore

_MARKDOWN = MarkdownIt("commonmark")
_CHECKBOXES = ("[ ]", "[x]", "[X]")
_VERIFICATION = "Verification:"
_CHANGE_DOCUMENTS = ("proposal.md", "design.md", "tasks.md")
_PROMPT = "roadmap_implement_step.md"


@dataclass(frozen=True)
class GroupTask:
    """One task of a group: its text with the checkbox, and whether it is ticked."""

    text: str
    ticked: bool
    verification: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class TaskGroup:
    """A numbered `##` section of a `tasks.md`: its tasks, and its text from its heading to the
    next `##` heading."""

    number: int
    title: str
    tasks: tuple[GroupTask, ...]
    text: str

    @property
    def verification_commands(self) -> tuple[str, ...]:
        """The code spans of the `Verification:` lines of the tasks, each once, in file order."""
        return tuple(dict.fromkeys(c for task in self.tasks for c in task.verification))

    @property
    def named_paths(self) -> tuple[str, ...]:
        """The code spans of the text of the tasks, each once: the files the group may name."""
        return tuple(dict.fromkeys(p for task in self.tasks for p in task.paths))


def _code_spans(inline: Token) -> tuple[str, ...]:
    """The code spans of an inline token."""
    return tuple(child.content for child in inline.children or () if child.type == "code_inline")


def _list_items(tokens: Sequence[Token]) -> Iterator[Sequence[Token]]:
    """The tokens of each top-level list item of `tokens`."""
    start = 0
    for index, token in enumerate(tokens):
        if token.type == "list_item_open" and token.level == 1:
            start = index
        elif token.type == "list_item_close" and token.level == 1:
            yield tokens[start : index + 1]


def _task_of(item: Sequence[Token]) -> GroupTask | None:
    """The task a list item is, or None when its text starts with no checkbox."""
    lines = [token for token in item if token.type == "inline"]
    if not lines or lines[0].content[:3] not in _CHECKBOXES:
        return None
    verification = tuple(
        command
        for line in lines[1:]
        if line.content.startswith(_VERIFICATION)
        for command in _code_spans(line)
    )
    return GroupTask(
        text=lines[0].content,
        ticked=lines[0].content[:3] != _CHECKBOXES[0],
        verification=verification,
        paths=_code_spans(lines[0]),
    )


def _headings(tokens: Sequence[Token], tag: str) -> list[tuple[int, int, str]]:
    """The index, the first line and the text of each heading of `tag`."""
    return [
        (index, token.map[0], tokens[index + 1].content)
        for index, token in enumerate(tokens)
        if token.type == "heading_open" and token.tag == tag and token.map is not None
    ]


def parse_task_groups(tasks_md: str) -> list[TaskGroup]:
    """The numbered groups of a `tasks.md`, in file order. A `##` section whose heading is not
    `<n>. <title>`, such as `## Workflow follow-up`, is no group, and ends the one before it."""
    tokens = _MARKDOWN.parse(tasks_md)
    lines = tasks_md.splitlines()
    headings = _headings(tokens, "h2")
    groups: list[TaskGroup] = []
    for position, (index, first_line, heading) in enumerate(headings):
        number, dot, title = heading.partition(". ")
        if not dot or not number.isdigit():
            continue
        last = headings[position + 1] if position + 1 < len(headings) else None
        end_index = last[0] if last else len(tokens)
        end_line = last[1] if last else len(lines)
        tasks = (_task_of(item) for item in _list_items(tokens[index:end_index]))
        groups.append(
            TaskGroup(
                number=int(number),
                title=title,
                tasks=tuple(task for task in tasks if task is not None),
                text="\n".join(lines[first_line:end_line]).rstrip(),
            )
        )
    return groups


def _section(body: str, titles: frozenset[str]) -> str:
    """The text of each section of `body` whose heading is one of `titles`, heading included.
    A section ends at the next heading of its level or a higher one."""
    tokens = _MARKDOWN.parse(body)
    lines = body.splitlines()
    marks = [
        (token.map[0], int(token.tag[1:]), tokens[index + 1].content)
        for index, token in enumerate(tokens)
        if token.type == "heading_open" and token.map is not None
    ]
    found: list[str] = []
    for position, (first, level, title) in enumerate(marks):
        if title.strip().casefold() not in titles:
            continue
        end = next(
            (start for start, deeper, _ in marks[position + 1 :] if deeper <= level), len(lines)
        )
        found.append("\n".join(lines[first:end]).rstrip())
    return "\n\n".join(found)


def issue_inputs(item: Item) -> str:
    """The title of the item, then its problem and its acceptance criteria. An issue that holds
    neither section gives its whole body."""
    wanted = CONST_ROADMAP_IMPLEMENT_PROBLEM_HEADINGS | CONST_ROADMAP_IMPLEMENT_CRITERIA_HEADINGS
    text = _section(item.body, wanted) or item.body.strip()
    return f"# Item #{item.number}: {item.title}\n\n{text}"


def find_change(source: Path, item: int) -> Path:
    """The one folder `openspec/changes/<item>-*/` of the checkout."""
    pattern = f"{item}-*"
    found = sorted(
        path for path in (source / CONST_OPENSPEC_CHANGES_DIR).glob(pattern) if path.is_dir()
    )
    if not found:
        raise RoadmapImplementError(MESSAGES.roadmap.implement_no_change.format(pattern=pattern))
    if len(found) > 1:
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_many_changes.format(
                pattern=pattern, names=", ".join(path.name for path in found)
            )
        )
    return found[0]


def _packed(path: Path) -> str:
    """A file for the inputs: a Python file as its signatures, any other as its start."""
    if path.suffix == ".py":
        config = PackingConfig(
            max_tokens=CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS, strip_private=False
        )
        return ContextPacker().pack_file(path, config=config).content
    text = path.read_text(encoding="utf-8", errors="replace")
    return truncate_to_token_limit(text, CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS)


def named_files(source: Path, group: TaskGroup) -> list[Path]:
    """The files of the checkout that the group names: each code span of its tasks that is an
    existing file inside the checkout. A span that names a file that does not exist yet is
    left out."""
    root = source.resolve()
    resolved = (Path(os.path.normpath(root / span)) for span in group.named_paths)
    return [path for path in resolved if path.is_relative_to(root) and os.path.isfile(path)]


@dataclass(frozen=True)
class StepInputs:
    """What one step gives the model: the instructions, the user message, and their tokens."""

    group: TaskGroup
    instructions: str
    message: str
    tokens: int


def _files_section(source: Path, group: TaskGroup) -> str:
    """The packed files of the group, each under its path."""
    parts = [
        f"## {path.relative_to(source.resolve())}\n\n```\n{_packed(path)}\n```"
        for path in named_files(source, group)
    ]
    return "# Files the group names (signatures only)\n\n" + "\n\n".join(parts) if parts else ""


def build_step_inputs(
    store: RoadmapStore, *, item: int, group: int, source: Path, window: int
) -> StepInputs:
    """The inputs of group `group` of item `item`, read from the checkout `source`.

    Raises `RoadmapImplementError` for an issue that is no Item, a change that is not in the
    checkout, a group the change lacks, and inputs that measure more than `window` minus
    `CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS` tokens.
    """
    held = store.item(item)
    if held is None:
        raise RoadmapImplementError(MESSAGES.roadmap.implement_not_item.format(number=item))
    change = find_change(source, item)
    documents = {name: (change / name).read_text(encoding="utf-8") for name in _CHANGE_DOCUMENTS}
    groups = parse_task_groups(documents["tasks.md"])
    chosen = next((candidate for candidate in groups if candidate.number == group), None)
    if chosen is None:
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_no_group.format(
                change=change.name,
                group=group,
                groups=", ".join(str(candidate.number) for candidate in groups) or "none",
            )
        )
    sections = [
        issue_inputs(held),
        *(f"# {name} of the change\n\n{text.strip()}" for name, text in documents.items()),
        f"# Your group\n\n{chosen.text}",
        _files_section(source, chosen),
    ]
    message = "\n\n".join(section for section in sections if section)
    instructions = load_task_prompt(_PROMPT)
    tokens = count_tokens(instructions) + count_tokens(message)
    limit = window - CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS
    if tokens > limit:
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_over_window.format(
                measured=tokens,
                limit=limit,
                window=window,
                reserve=CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS,
            )
        )
    return StepInputs(group=chosen, instructions=instructions, message=message, tokens=tokens)
