"""The mechanical rewrite of a merged plan (#3556).

A plan that the stage job wrote before a gate existed can fail that gate today. Three edits fix
most of these plans, and each one is mechanical:

- A group with no `Verification:` line gets one under its first task. The command comes from the
  plan: `uv run devops ci test` with the test files of the `Changes:` line, or `uv run devops ci
  docs` when the group changes only documents. A command that the step refuses is not written, and
  a group that names neither gets no line.
- A path in a task text that the tree lacks, and that no group lists or creates, is a sample path
  that a test writes at run time. It becomes a bare name, as the stage prompt asks.
- A folder with no `design.md` gets a stub.

The rewrite works on the groups of `parse_task_groups` and edits by their line numbers, so every
other line stays as it is. It judges nothing: `devops roadmap plan-recheck` reads the rewritten
files with the same reader and gates as any other plan, and calls the folder `rewrite` only when
they pass.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement_shell_policy import verification_problem
from devops_cli.roadmap.plan_read import PlanReadError, created_paths, group_files
from devops_cli.roadmap.stage_paths import StagedTree
from devops_cli.roadmap.step_files import TaskGroup, file_lines, parse_task_groups

_DESIGN: Final[str] = "design.md"
_TASKS: Final[str] = "tasks.md"
_TEST_COMMAND: Final[str] = "uv run devops ci test"
_DOCS_COMMAND: Final[str] = "uv run devops ci docs"
# The test files that one command line can name without a quote.
_PLAIN_PATH: Final[re.Pattern[str]] = re.compile(r"[\w./-]+")
_VERIFICATION_LINE: Final[re.Pattern[str]] = re.compile(r"^\s*[-*+]\s+Verification:")


@dataclass(frozen=True)
class FileChange:
    """One file of a rewrite: its path from the repository root, its text before (None for a file
    that the rewrite adds), and its text after."""

    path: str
    before: str | None
    after: str


@dataclass(frozen=True)
class PlanRewrite:
    """The rewrite of one change folder: all its files after the rewrite, the files that differ
    from the folder (`changes`), and one note for each edit."""

    files: dict[str, str]
    changes: tuple[FileChange, ...]
    notes: tuple[str, ...]


def _listed(path: str, known: set[str]) -> bool:
    """Whether a group lists or creates `path`, or a file under it."""
    return any(other == path or other.startswith(f"{path}/") for other in known)


def _known_paths(groups: Sequence[TaskGroup], tasks_md: str) -> set[str]:
    """The paths that a group lists in `Reads:` or `Changes:`, and the paths that a text marks
    `(new)`. A group with no such line lists none."""
    known = set(created_paths(tasks_md))
    for group in groups:
        try:
            listed = group_files(group.text)
        except PlanReadError:
            continue
        known.update(listed.reads, listed.changes)
    return known


def _task_lines(group: TaskGroup, index: int, lines: Sequence[str]) -> range:
    """The lines of task `index` of `group`: from its line to the line before the next task or the
    end of the group, without the blank lines at the end."""
    start = group.tasks[index].line
    end = (
        group.tasks[index + 1].line
        if index + 1 < len(group.tasks)
        else group.line + len(group.text.split("\n"))
    )
    while end - 1 > start and not lines[end - 1].strip():
        end -= 1
    return range(start, end)


def _bare_names(group: TaskGroup, lines: list[str], tree: StagedTree, known: set[str]) -> list[str]:
    """Change each sample path of the tasks of `group` to its bare name, in `lines`. A
    `Verification:` line stays as it is. Returns one note for each path."""
    texts = MESSAGES.roadmap
    notes: list[str] = []
    for index, task in enumerate(group.tasks):
        if task.line < 0:
            continue
        for span in dict.fromkeys(task.paths):
            path = tree.as_path(span)
            if path is None or tree.has(path) or _listed(path, known):
                continue
            name = PurePosixPath(path).name
            for number in _task_lines(group, index, lines):
                if not _VERIFICATION_LINE.match(lines[number]):
                    lines[number] = lines[number].replace(f"`{span}`", f"`{name}`")
            notes.append(
                texts.plan_rewrite_note_path.format(group=group.number, path=path, name=name)
            )
    return notes


def _command(group: TaskGroup) -> str | None:
    """The command that proves `group`, from the plan, or None when the plan gives none: the tests
    of the `Changes:` line, else the documents check for a group that changes only documents. The
    step must be able to run the command."""
    try:
        changes = group_files(group.text).changes
    except PlanReadError:
        return None
    if not all(_PLAIN_PATH.fullmatch(path) for path in changes):
        return None
    tests = [p for p in dict.fromkeys(changes) if p.startswith("tests/") and p.endswith(".py")]
    if tests:
        command = f"{_TEST_COMMAND} {' '.join(tests)}"
    elif changes and all(path.endswith(".md") for path in changes):
        command = _DOCS_COMMAND
    else:
        return None
    return command if verification_problem(command) is None else None


def _verification(group: TaskGroup, lines: Sequence[str]) -> tuple[int, str, str] | None:
    """The line to add to `group`, as the number of the line to add it after, the text of the line
    and the note. None when the group has a `Verification:` line or the plan gives no command."""
    if group.verification_commands or not group.tasks or group.tasks[0].line < 0:
        return None
    command = _command(group)
    if command is None:
        return None
    texts = MESSAGES.roadmap
    template = texts.stage_task_test if group.is_behavior else texts.stage_task_pass
    text = template.partition("\n")[2].format(verify=command)
    after = _task_lines(group, 0, lines)[-1]
    note = texts.plan_rewrite_note_verification.format(group=group.number, command=command)
    return after, text, note


def _insert(lines: list[str], after: int, text: str) -> None:
    """Add the line `text` after line `after`, with the line end of that line."""
    end = lines[after][len(lines[after].rstrip("\r\n")) :]
    if end:
        lines.insert(after + 1, text + end)
    else:
        lines[after] += "\n"
        lines.insert(after + 1, text)


def _rewrite_tasks(tasks_md: str, tree: StagedTree) -> tuple[str, list[str]]:
    """The text of `tasks.md` after the rewrite, and one note for each edit."""
    groups = parse_task_groups(tasks_md)
    lines = file_lines(tasks_md)
    known = _known_paths(groups, tasks_md)
    notes: list[str] = []
    for group in groups:
        notes.extend(_bare_names(group, lines, tree, known))
    added = [found for group in groups if (found := _verification(group, lines)) is not None]
    for after, text, _ in sorted(added, reverse=True):
        _insert(lines, after, text)
    notes.extend(note for _, _, note in sorted(added))
    return "".join(lines), notes


def rewrite_plan(root: str, files: Mapping[str, str], tree: StagedTree) -> PlanRewrite:
    """Rewrite the change folder `root` (a path from the repository root) in `files`. `tree` is
    the tracked files of the commit that the plan is judged on. The result holds all the files of
    the folder, and the files that differ. A plan that needs no change comes back as it was."""
    rewritten = dict(files)
    notes: list[str] = []
    design = f"{root}/{_DESIGN}"
    if design not in rewritten:
        rewritten[design] = MESSAGES.roadmap.plan_rewrite_design_stub
        notes.append(MESSAGES.roadmap.plan_rewrite_note_design)
    tasks = f"{root}/{_TASKS}"
    if tasks in files:
        rewritten[tasks], found = _rewrite_tasks(files[tasks], tree)
        notes.extend(found)
    changes = tuple(
        FileChange(path, files.get(path), text)
        for path, text in sorted(rewritten.items())
        if files.get(path) != text
    )
    return PlanRewrite(rewritten, changes, tuple(notes))


__all__ = ["FileChange", "PlanRewrite", "rewrite_plan"]
