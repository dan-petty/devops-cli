"""The form of the commands and the new test files of a plan (#3015).

About 14 of 37 plans of 2026-11-01 gave `uv run pytest <file>` as the `verify` command, and about 6
put a new test file flat under `tests/`. `docs/TESTING.md` says a check runs with `uv run devops`
and the tests mirror the package tree of `src/devops_cli`. `form_problems` finds both faults in
the reply, so the model corrects them in the one retry.

A `verify` command starts with `uv run devops`, or is the `! git grep -n <name>` check that a name
is gone, which `docs/TESTING.md` names for a deletion and no `devops` command replaces. A new test
module (`tests/**/test_*.py` in `creates`) sits in the directory that mirrors the package of a
source file that the plan changes, or in `tests/invariants/`. A plan that changes no source file
has no package to mirror, so it only refuses a test module directly under `tests/`. A file under
`tests/` that is no test module (a fixture, a helper, a `conftest.py`) is not judged.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Final

from devops_cli.lang import MESSAGES

if TYPE_CHECKING:
    from devops_cli.roadmap.stage_change import StageGroup

_VERIFY_PREFIX: Final[str] = "uv run devops"
_NEGATIVE_SEARCH_PREFIX: Final[str] = "! git grep "
_TESTS: Final[PurePosixPath] = PurePosixPath("tests")
_INVARIANTS: Final[PurePosixPath] = _TESTS / "invariants"
_PACKAGE: Final[PurePosixPath] = PurePosixPath("src/devops_cli")
_TEST_MODULE_PREFIX: Final[str] = "test_"
_PYTHON_SUFFIX: Final[str] = ".py"


def _valid_verify(command: str) -> bool:
    """Whether `command` starts with `uv run devops` as a whole word, or is a negative search."""
    command = command.strip()
    return command == _VERIFY_PREFIX or command.startswith(
        (f"{_VERIFY_PREFIX} ", _NEGATIVE_SEARCH_PREFIX)
    )


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
        if group.verify is not None and not _valid_verify(group.verify):
            problems.append(
                texts.stage_problem_verify.format(group=number, command=group.verify.strip())
            )
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
