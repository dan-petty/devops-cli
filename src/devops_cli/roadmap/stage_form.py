"""The form of the commands and the new test files of a plan (#3015).

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
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Final

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_SEARCH_CHARS
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement_shell_policy import (
    NEGATIVE_SEARCH_WORD,
    shown,
    verification_problem,
)

if TYPE_CHECKING:
    from devops_cli.roadmap.stage_change import StageGroup

_VERIFY_PREFIX: Final[str] = "uv run devops"
_TESTS: Final[PurePosixPath] = PurePosixPath("tests")
_INVARIANTS: Final[PurePosixPath] = _TESTS / "invariants"
_PACKAGE: Final[PurePosixPath] = PurePosixPath("src/devops_cli")
_TEST_MODULE_PREFIX: Final[str] = "test_"
_PYTHON_SUFFIX: Final[str] = ".py"


def _verify_problem(number: int, command: str) -> str | None:
    """The problem of the `verify` command of group `number`, or None when it has the project form
    and the step runs it. A command of another form gets the forms to use. A command of the project
    form that the step refuses gets the reason of the step."""
    command = command.strip()
    named = shown(command, CONST_ROADMAP_IMPLEMENT_SEARCH_CHARS)
    texts = MESSAGES.roadmap
    if "`" in command:
        return texts.stage_problem_verify_backtick.format(group=number, command=named)
    first = command.split(maxsplit=1)[0] if command else ""
    if first != NEGATIVE_SEARCH_WORD and not (
        command == _VERIFY_PREFIX or command.startswith(f"{_VERIFY_PREFIX} ")
    ):
        return texts.stage_problem_verify.format(group=number, command=named)
    if (reason := verification_problem(command)) is None:
        return None
    return texts.stage_problem_verify_run.format(group=number, command=named, reason=reason)


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


def form_problems(groups: Sequence[StageGroup]) -> list[str]:
    """One sentence for each `verify` command that is not in the project form, and for each new
    test module outside the mirror directories and `tests/invariants/`."""
    texts = MESSAGES.roadmap
    mirrors = _mirror_directories(groups)
    problems: list[str] = []
    for number, group in enumerate(groups, start=1):
        if group.verify is not None and (problem := _verify_problem(number, group.verify)):
            problems.append(problem)
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
