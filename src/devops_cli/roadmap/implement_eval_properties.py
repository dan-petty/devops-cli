"""The properties of a good result of an implement step (#3030).

Four come from a diff and the plan alone, so they run anywhere, also in CI with no git history:
`tests_kept`, `diff_scope`, `no_scratch` and `tasks_ticked`. `unidiff` reads the diff. Two run
commands in the tree of the result: `tests_pass` runs the commands that name the tests, and
`verify_passes` runs the verification commands of the group, with the allowlist of the step.

Each property is pass, fail or skipped, with a detail that names what failed. A diff that the step
cut leaves the four diff properties skipped, and a step that stopped has no tree, so it leaves
the two command properties skipped.

`tests_kept` reads the names on the removed and the added lines of each Python file under `tests/`,
so it has the limits of `implement_test_names` and one more: a name has no class, because a hunk
does not show it. A test that moves to another class of its file is kept.
"""

from __future__ import annotations

import textwrap
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pathspec import GitIgnoreSpec
from unidiff.errors import UnidiffParseError
from unidiff.patch import PatchedFile, PatchSet

from devops_cli.config.constants import (
    CONST_ROADMAP_EVAL_DETAIL_NAMES,
    CONST_ROADMAP_EVAL_SCRATCH_PATTERNS,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement_eval import (
    COMMAND_PROPERTIES,
    DIFF_PROPERTIES,
    LoadedCase,
    Property,
)
from devops_cli.roadmap.implement_step import commands_failure
from devops_cli.roadmap.step_files import file_lines, parse_task_groups

_SCRATCH = GitIgnoreSpec.from_lines(CONST_ROADMAP_EVAL_SCRATCH_PATTERNS)
_TESTS_DIR = "tests/"
_TEST_PREFIX = "test_"
_TASK_CHARS = 60


class Status(StrEnum):
    """How a property ended."""

    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class PropertyResult:
    """A property, how it ended, and what failed or why it did not run."""

    prop: Property
    status: Status
    detail: str = ""


def skipped(props: Iterable[Property], reason: str) -> list[PropertyResult]:
    """Each of `props` as skipped, with `reason`."""
    return [PropertyResult(prop, Status.SKIPPED, reason) for prop in props]


def _outcome(prop: Property, problem: str) -> PropertyResult:
    """The property as failed with `problem`, or passed when it is empty."""
    return PropertyResult(prop, Status.FAIL if problem else Status.PASS, problem)


def _listed(names: Sequence[str]) -> str:
    """`names` as one line, cut to `CONST_ROADMAP_EVAL_DETAIL_NAMES` names with the count of the
    rest."""
    shown = list(names[:CONST_ROADMAP_EVAL_DETAIL_NAMES])
    line = ", ".join(shown)
    rest = len(names) - len(shown)
    return line + (MESSAGES.roadmap.eval_implement_more.format(count=rest) if rest else "")


def _test_name(line: str) -> str | None:
    """The name of the test that a line of source defines, or None."""
    words = line.split()
    if words[:1] == ["async"]:
        words = words[1:]
    if len(words) < 2 or words[0] != "def":
        return None
    name = words[1].partition("(")[0]
    return name if name.startswith(_TEST_PREFIX) and name.isidentifier() else None


def _test_names(lines: Iterable[str]) -> set[str]:
    return {name for line in lines if (name := _test_name(line)) is not None}


def _is_test_file(path: str) -> bool:
    return path.startswith(_TESTS_DIR) and path.endswith(".py")


def _lines(file: PatchedFile, *, added: bool) -> list[str]:
    return [
        line.value
        for hunk in file
        for line in hunk
        if (line.is_added if added else line.is_removed)
    ]


def _tests_kept(loaded: LoadedCase, patch: PatchSet) -> PropertyResult:
    lost: list[str] = []
    for file in patch:
        if _is_test_file(file.path):
            gone = _test_names(_lines(file, added=False)) - _test_names(_lines(file, added=True))
            lost += [f"{file.path}::{name}" for name in sorted(gone)]
    lost = [entry for entry in lost if entry not in loaded.case.allow_lost_tests]
    problem = MESSAGES.roadmap.eval_implement_lost_tests.format(names=_listed(lost)) if lost else ""
    return _outcome(Property.TESTS_KEPT, problem)


def _diff_scope(loaded: LoadedCase, patch: PatchSet) -> PropertyResult:
    allowed = {*loaded.case.changes, loaded.tasks_path}
    outside = sorted({file.path for file in patch} - allowed)
    problem = (
        MESSAGES.roadmap.eval_implement_outside.format(names=_listed(outside)) if outside else ""
    )
    return _outcome(Property.DIFF_SCOPE, problem)


def _is_scratch(path: str) -> bool:
    return "/" not in path or _SCRATCH.match_file(path)


def _no_scratch(loaded: LoadedCase, patch: PatchSet) -> PropertyResult:
    found = sorted(
        file.path
        for file in patch
        if file.is_added_file and file.path not in loaded.case.changes and _is_scratch(file.path)
    )
    problem = MESSAGES.roadmap.eval_implement_scratch.format(names=_listed(found)) if found else ""
    return _outcome(Property.NO_SCRATCH, problem)


class _HunkMismatch(ValueError):
    """A hunk of the diff that the text does not hold."""


def _apply(text: str, file: PatchedFile) -> str:
    """`text` with the hunks of `file` applied: each hunk replaces its source lines with its target
    lines. Raises `_HunkMismatch` when the text lacks the source lines of a hunk."""
    lines = file_lines(text)
    for hunk in reversed(list(file)):
        start = hunk.source_start - 1 if hunk.source_length else hunk.source_start
        source = [line.value for line in hunk.source_lines()]
        if lines[start : start + len(source)] != source:
            raise _HunkMismatch(file.path)
        lines[start : start + len(source)] = [line.value for line in hunk.target_lines()]
    return "".join(lines)


def _tasks_ticked(loaded: LoadedCase, patch: PatchSet) -> PropertyResult:
    texts = MESSAGES.roadmap
    text = loaded.plan["tasks.md"]
    try:
        for file in patch:
            if file.path == loaded.tasks_path:
                text = _apply(text, file)
    except _HunkMismatch as exc:
        return _outcome(Property.TASKS_TICKED, texts.eval_implement_hunk.format(path=exc))
    group = next((g for g in parse_task_groups(text) if g.number == loaded.case.group), None)
    if group is None:
        problem = texts.eval_implement_group_gone.format(group=loaded.case.group)
    else:
        open_tasks = [textwrap.shorten(t.text, _TASK_CHARS) for t in group.tasks if not t.ticked]
        problem = (
            texts.eval_implement_unticked.format(names=_listed(open_tasks)) if open_tasks else ""
        )
    return _outcome(Property.TASKS_TICKED, problem)


def diff_results(loaded: LoadedCase, diff: str, *, cut: bool = False) -> list[PropertyResult]:
    """The four properties that a diff decides, in the order of `DIFF_PROPERTIES`. `cut` says that
    the step cut the diff: the properties are skipped. A diff that does not parse fails them all."""
    texts = MESSAGES.roadmap
    if cut:
        return skipped(DIFF_PROPERTIES, texts.eval_implement_cut)
    try:
        patch = PatchSet(diff)
    except UnidiffParseError as exc:
        problem = texts.eval_implement_unparsed.format(reason=exc)
        return [PropertyResult(prop, Status.FAIL, problem) for prop in DIFF_PROPERTIES]
    return [
        _tests_kept(loaded, patch),
        _diff_scope(loaded, patch),
        _no_scratch(loaded, patch),
        _tasks_ticked(loaded, patch),
    ]


def _commands(prop: Property, source: Path, commands: Sequence[str]) -> PropertyResult:
    if not commands:
        return PropertyResult(prop, Status.SKIPPED, MESSAGES.roadmap.eval_implement_no_commands)
    return _outcome(prop, commands_failure(source, commands) or "")


def command_results(loaded: LoadedCase, source: Path) -> list[PropertyResult]:
    """The two properties that run commands in the tree `source`, in the order of
    `COMMAND_PROPERTIES`."""
    tests = _commands(Property.TESTS_PASS, source, loaded.case.tests_pass)
    verify = _commands(Property.VERIFY_PASSES, source, loaded.group.verification_commands)
    return [tests, verify]


def no_tree(reason: str) -> list[PropertyResult]:
    """The two command properties of a step that stopped: skipped, with the reason of the stop."""
    return skipped(
        COMMAND_PROPERTIES, MESSAGES.roadmap.eval_implement_no_tree.format(reason=reason)
    )
