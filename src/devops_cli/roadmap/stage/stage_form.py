"""The form of the tasks, the commands and the new test files of a plan (#3015, #3255).

About 14 of 37 plans of 2026-11-01 gave `uv run pytest <file>` as the `verify` command, and about 6
put a new test file flat under `tests/`. `docs/TESTING.md` says a check runs with `uv run devops`
and the tests mirror the package tree of `src/devops_cli`. `form_problems` finds both faults in
the reply, so the model corrects them in the one retry.

A `verify` command starts with `uv run devops`, or is the `! git grep -n <name> src/ tests/` check
that a name is gone, which `docs/TESTING.md` names for a deletion and no `devops` command replaces.
The step must run the command (#3263), so the gate asks `verification_problem` of the shell
policy, the table that the step reads, and a command that the step refuses gets the reason of the
step. A new test module (`tests/**/test_*.py` in `creates`) sits in the directory that mirrors the
package of a source file that the plan changes, or in `tests/invariants/`. A plan that changes no
source file has no package to mirror, so it only refuses a test module directly under `tests/`. A
file under `tests/` that is no test module (a fixture, a helper, a `conftest.py`) is not judged.

A task text holds more than one word, with a code span as one word. A path or a word alone says
nothing to the step: `tests/roadmap/test_stage.py` is no task, and `Add a test in
tests/roadmap/test_stage.py for a bare task` is one (#3255). The gate counts words and parses no
grammar, so a sentence with a verb and an object always passes.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable, Mapping, Sequence
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Final

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement_shell_policy import (
    NEGATIVE_SEARCH_WORD,
    NegativeSearch,
    read_negative_search,
    shown,
    verification_problem,
)

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage_change import StageGroup

_VERIFY_PREFIX: Final[str] = "uv run devops"
_TESTS: Final[PurePosixPath] = PurePosixPath("tests")
_INVARIANTS: Final[PurePosixPath] = _TESTS / "invariants"
_PACKAGE: Final[PurePosixPath] = PurePosixPath("src/devops_cli")
_TEST_MODULE_PREFIX: Final[str] = "test_"
_PYTHON_SUFFIX: Final[str] = ".py"
_CODE_SPAN: Final[re.Pattern[str]] = re.compile(r"`[^`]*`")
_CASE_SUFFIXES: Final[tuple[str, ...]] = (
    "_test.yaml",
    "_tests.yaml",
    "_test.yml",
    "_tests.yml",
)
_MANIFEST_VERIFY_PREFIX: Final[str] = "uv run devops ci test"


def _is_case_path(path: str | PurePosixPath) -> bool:
    """Whether `path` names a test case file by its suffix."""
    return PurePosixPath(path).name.endswith(_CASE_SUFFIXES)


def is_valid_verify(command: str) -> bool:
    """Whether `command` starts with `uv run devops` as a whole word."""
    command = command.strip()
    return command == _VERIFY_PREFIX or command.startswith(f"{_VERIFY_PREFIX} ")


def _verify_problems(number: int, command: str) -> list[str]:
    """The problems of the `verify` command of group `number`: a backtick, which ends the code span
    that the plan writes it in, and a form that the step does not run. A command of the project
    form that the step refuses gets the reason of the step. A command with both faults gets both
    problems, as the job asks the model once."""
    command = command.strip()
    named = shown(command, CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS)
    texts = MESSAGES.roadmap
    problems: list[str] = []
    if "`" in command:
        problems.append(texts.stage_problem_verify_backtick.format(group=number, command=named))
    first = command.split(maxsplit=1)[0] if command else ""
    if first != NEGATIVE_SEARCH_WORD and not is_valid_verify(command):
        problems.append(texts.stage_problem_verify.format(group=number, command=named))
    elif (reason := verification_problem(command)) is not None:
        problems.append(
            texts.stage_problem_verify_run.format(group=number, command=named, reason=reason)
        )
    return problems


def _manifest_verify_problems(number: int, group: StageGroup) -> list[str]:
    """The problem of the `verify` command of a `manifest` group: it must be `uv run devops ci test`
    followed by one path of the group or its folder."""
    if group.kind != "manifest" or group.verify is None:
        return []
    command = group.verify.strip()
    try:
        words = shlex.split(command)
    except ValueError:
        words = command.split()
    prefix_words = _MANIFEST_VERIFY_PREFIX.split()
    named = shown(command, CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS)
    texts = MESSAGES.roadmap
    if len(words) != len(prefix_words) + 1 or words[: len(prefix_words)] != prefix_words:
        return [texts.stage_problem_manifest_verify.format(group=number, command=named)]
    target = PurePosixPath(words[-1])
    group_paths = {PurePosixPath(p) for p in (*group.changes, *group.creates, *group.reads)}
    allowed = group_paths | {p.parent for p in group_paths if p.parent != PurePosixPath(".")}
    if target not in allowed:
        return [texts.stage_problem_manifest_verify.format(group=number, command=named)]
    return []


def _task_problems(number: int, group: StageGroup) -> list[str]:
    """One problem for each task text of group `number` that holds one word or less: the failing
    test, the work and the document task. A code span counts as one word."""
    texts = MESSAGES.roadmap
    parts = (
        ("test", group.test),
        ("implementation", group.implementation),
        ("documentation", group.documentation),
    )
    return [
        texts.stage_problem_task.format(
            group=number,
            title=group.title,
            part=part,
            text=shown(text, CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS),
        )
        for part, text in parts
        if text is not None and len(_CODE_SPAN.sub("x", text).split()) < 2
    ]


def _mirror_directories(groups: Sequence[StageGroup]) -> list[PurePosixPath]:
    """The test directory of each source file that any group changes, sorted and without a
    repeat. The directory of a module at the top of the package is `tests` itself."""
    mirrors: set[PurePosixPath] = set()
    for group in groups:
        for path in map(PurePosixPath, group.changes):
            if path.suffix == _PYTHON_SUFFIX and path.is_relative_to(_PACKAGE):
                mirrors.add(_TESTS / path.parent.relative_to(_PACKAGE))
    return sorted(mirrors)


def _is_test_module(path: PurePosixPath) -> bool:
    return (
        path.is_relative_to(_TESTS)
        and path.suffix == _PYTHON_SUFFIX
        and path.name.startswith(_TEST_MODULE_PREFIX)
    )


def _expected(mirrors: Sequence[PurePosixPath]) -> str:
    """The directories a new test may go in, as code spans, for the text of a problem."""
    allowed = [*(m for m in mirrors if m != _TESTS), _INVARIANTS]
    return " or ".join(f"`{directory}`" for directory in allowed)


def negative_search_parts(command: str) -> NegativeSearch | None:
    """The literal and the relative paths of a negative-search `command`, or None for a command
    of another shape. It reads the same grammar as the step (`read_negative_search`)."""
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    found = read_negative_search(words)
    return None if isinstance(found, str) else found


def record_search_evidence(
    groups: Sequence[StageGroup], search: Callable[[str], Sequence[str]]
) -> dict[str, tuple[str, ...]]:
    """The paths that `search` finds for each negative-search literal of `groups`. It calls
    `search` once for each literal, so the job records the staged hits before it judges the
    reply."""
    evidence: dict[str, tuple[str, ...]] = {}
    for group in groups:
        if group.verify is None:
            continue
        found = negative_search_parts(group.verify)
        if found is None:
            continue
        for literal in found.literals:
            if literal in evidence:
                continue
            evidence[literal] = tuple(sorted({path for path in search(literal) if path}))
    return evidence


def _import_path(path: PurePosixPath) -> str | None:
    """The import path of a Python source path under `src/devops_cli`, or None for another
    path."""
    if path.suffix != _PYTHON_SUFFIX or not path.is_relative_to(_PACKAGE):
        return None
    parts = list(path.relative_to(_PACKAGE).with_suffix("").parts)
    if parts[-1:] == ["__init__"]:
        del parts[-1]
    return ".".join(("devops_cli", *parts))


def search_problems(
    groups: Sequence[StageGroup],
    evidence: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """One sentence for each negative-search literal with no recorded hit, and for each literal
    that the import path of a created source path contains. `evidence` maps each literal to the
    paths that the staged tree holds; None means the caller recorded no search, so the check
    judges only the created paths."""
    texts = MESSAGES.roadmap
    created = [
        (path, import_path)
        for group in groups
        for path in group.creates
        if (import_path := _import_path(PurePosixPath(path))) is not None
    ]
    problems: list[str] = []
    for number, group in enumerate(groups, start=1):
        if group.verify is None:
            continue
        found = negative_search_parts(group.verify)
        if found is None:
            continue
        for literal in found.literals:
            kept = next(((path, name) for path, name in created if literal in name), None)
            if kept is not None:
                path, import_path = kept
                problems.append(
                    texts.stage_problem_search_created.format(
                        group=number,
                        command=group.verify,
                        literal=literal,
                        path=path,
                        import_path=import_path,
                    )
                )
            if evidence is not None and not evidence.get(literal):
                problems.append(
                    texts.stage_problem_search_no_hit.format(
                        group=number, command=group.verify, literal=literal
                    )
                )
    return problems


def form_problems(groups: Sequence[StageGroup]) -> list[str]:
    """One sentence for each task text of one word, for each `verify` command that is not in the
    project form, and for each new test module outside the mirror directories and
    `tests/invariants/`."""
    texts = MESSAGES.roadmap
    mirrors = _mirror_directories(groups)
    problems: list[str] = []
    for number, group in enumerate(groups, start=1):
        problems.extend(_task_problems(number, group))
        if group.verify is not None:
            problems.extend(_verify_problems(number, group.verify))
        problems.extend(_manifest_verify_problems(number, group))
        if group.kind == "other":
            for case_path in (*group.changes, *group.creates):
                if _is_case_path(case_path):
                    problems.append(
                        texts.stage_problem_manifest_kind.format(group=number, path=case_path)
                    )
                    break
        for created in group.creates:
            path = PurePosixPath(created)
            folder = path.parent
            allowed = folder == _INVARIANTS or (folder in mirrors if mirrors else folder != _TESTS)
            if _is_test_module(path) and not allowed:
                problems.append(
                    texts.stage_problem_test_path.format(
                        group=number, path=created, directory=folder, expected=_expected(mirrors)
                    )
                )
    return problems
