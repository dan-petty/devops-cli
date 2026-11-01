"""What an implement step reads of the checkout, and what the stage job counts for it.

A `tasks.md` holds numbered groups (`## <n>. <title>`), and a step runs one group. The step reads
the files that the tasks of the group name in code spans, each packed to at most
`CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens, and opens the rest with its tools. The stage job
measures a task group with the same parser, the same files and the same text, so a group costs in
the plan what its step reads.
"""

from __future__ import annotations

import io
import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token

from devops_cli.ai.context_budget import truncate_to_token_limit
from devops_cli.ai.context_packer import ContextPacker, PackingConfig
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS

MARKDOWN = MarkdownIt("commonmark")
CHECKBOXES = ("[ ]", "[x]", "[X]")
_VERIFICATION = "Verification:"


@dataclass(frozen=True)
class GroupTask:
    """One task of a group: its text with the checkbox, and whether it is ticked. `line` is the
    zero-based line of the task in its file, or -1 for a task that no file holds. It is no part of
    the comparison: a blank line that moves a task changes no task."""

    text: str
    ticked: bool
    verification: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    line: int = field(default=-1, compare=False)


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


def code_spans(text: str) -> tuple[str, ...]:
    """The code spans of `text`, a line of inline markdown, in order."""
    return tuple(span for token in MARKDOWN.parseInline(text) for span in _code_spans(token))


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
    if not lines or lines[0].content[:3] not in CHECKBOXES:
        return None
    verification = tuple(
        command
        for line in lines[1:]
        if line.content.startswith(_VERIFICATION)
        for command in _code_spans(line)
    )
    return GroupTask(
        text=lines[0].content,
        ticked=lines[0].content[:3] != CHECKBOXES[0],
        verification=verification,
        paths=_code_spans(lines[0]),
        line=lines[0].map[0] if lines[0].map else -1,
    )


def _headings(tokens: Sequence[Token], tag: str) -> list[tuple[int, int, str]]:
    """The index, the first line and the text of each heading of `tag`."""
    return [
        (index, token.map[0], tokens[index + 1].content)
        for index, token in enumerate(tokens)
        if token.type == "heading_open" and token.tag == tag and token.map is not None
    ]


def file_lines(text: str) -> list[str]:
    """The lines of `text` with their line ends, split as markdown-it splits: at `\\n`, `\\r` and
    `\\r\\n`, and nowhere else. `"".join` of the lines is `text`. The line numbers of the tokens
    index this list."""
    return io.StringIO(text, newline="").readlines()


def parse_task_groups(tasks_md: str) -> list[TaskGroup]:
    """The numbered groups of a `tasks.md`, in file order. A `##` section whose heading is not
    `<n>. <title>`, such as `## Workflow follow-up`, is no group, and ends the one before it."""
    tokens = MARKDOWN.parse(tasks_md)
    lines = [line.rstrip("\r\n") for line in file_lines(tasks_md)]
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


def named_files(source: Path, group: TaskGroup) -> list[Path]:
    """The files of the checkout that the group names: each code span of its tasks that is an
    existing file inside the checkout. A span that names a file that does not exist yet is
    left out."""
    root = source.resolve()
    resolved = (Path(os.path.normpath(root / span)) for span in group.named_paths)
    return [path for path in resolved if path.is_relative_to(root) and os.path.isfile(path)]


def packed_file(path: Path) -> str:
    """A file for the inputs: a Python file as its signatures, any other as its start."""
    if path.suffix == ".py":
        config = PackingConfig(
            max_tokens=CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS, strip_private=False
        )
        return ContextPacker().pack_file(path, config=config).content
    text = path.read_text(encoding="utf-8", errors="replace")
    return truncate_to_token_limit(text, CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS)


__all__ = [
    "CHECKBOXES",
    "MARKDOWN",
    "GroupTask",
    "TaskGroup",
    "code_spans",
    "file_lines",
    "named_files",
    "packed_file",
    "parse_task_groups",
]
