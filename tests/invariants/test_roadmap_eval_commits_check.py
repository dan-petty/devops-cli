"""The base commit of each golden eval case: the `roadmap-eval-commits` row of `devops ci`
(#4449, #5516).

git gives the shallow answer and resolves each base commit of both the stage and implement golden
sets, so these cases give the row canned answers and no test starts git. The real sets give the
count of cases and each note.
"""

from __future__ import annotations

import pytest

from devops_cli.config.constants import CONST_ROADMAP_EVAL_IMPLEMENT_FIXTURES
from devops_cli.roadmap.implement.implement_eval import (
    LoadedCase,
)
from devops_cli.roadmap.implement.implement_eval import (
    load_cases as load_implement_cases,
)
from devops_cli.roadmap.stage.stage_eval_cases import (
    CASES_DIRECTORY,
    NO_COMMIT,
    StageCase,
)
from devops_cli.roadmap.stage.stage_eval_cases import (
    load_cases as load_stage_cases,
)
from tests.gate.roadmap_eval_commits import is_shallow, outcome
from tests.support.paths import REPO_ROOT


@pytest.fixture(scope="module")
def stage_cases() -> list[StageCase]:
    return load_stage_cases(REPO_ROOT / CASES_DIRECTORY)


@pytest.fixture(scope="module")
def implement_cases() -> list[LoadedCase]:
    return load_implement_cases(REPO_ROOT / CONST_ROADMAP_EVAL_IMPLEMENT_FIXTURES)


def _resolves_everything(sha: str) -> bool:
    return True


def _resolves_nothing(sha: str) -> bool:
    return False


def test_the_row_fails_on_a_shallow_clone(
    stage_cases: list[StageCase], implement_cases: list[LoadedCase]
) -> None:
    """A shallow clone lacks the history that the cases need, so the row says so and fails."""
    total = len(stage_cases) + len(implement_cases)

    assert outcome(stage_cases, implement_cases, True, _resolves_everything) == (
        1,
        [
            "roadmap-eval-commits: the shallow clone lacks the history that the golden "
            f"cases need ({total} cases). Fetch it with `git fetch --unshallow`."
        ],
    )


def test_the_row_names_each_base_commit_that_git_cannot_resolve(
    stage_cases: list[StageCase], implement_cases: list[LoadedCase]
) -> None:
    """A base commit that git does not resolve gives a line with the case name and the hash."""
    committed = [case for case in stage_cases if case.base_commit != NO_COMMIT]
    total = len(stage_cases) + len(implement_cases)
    bad = len(committed) + len(implement_cases)

    status, lines = outcome(stage_cases, implement_cases, False, _resolves_nothing)

    assert (status, lines) == (
        1,
        [
            *(
                f"roadmap-eval-commits: {case.name}: {case.base_commit} is not a commit of "
                "the repository"
                for case in committed
            ),
            *(
                f"roadmap-eval-commits: {case.name}: {case.case.base} is not a commit of "
                "the repository"
                for case in implement_cases
            ),
            f"roadmap-eval-commits: {bad} of {total} cases name a base "
            "commit that the row refuses.",
        ],
    )


def test_the_row_names_a_stage_case_that_reads_no_commit_with_no_note(
    stage_cases: list[StageCase],
) -> None:
    """A stage case with NO_COMMIT passes only with a note that says that it reads no commit."""
    case = stage_cases[0].model_copy(update={"base_commit": NO_COMMIT, "notes": ()})

    assert outcome([case], [], False, _resolves_everything) == (
        1,
        [
            f"roadmap-eval-commits: {case.name}: its base commit is NO_COMMIT and no note "
            "says that it reads no commit",
            "roadmap-eval-commits: 1 of 1 cases name a base commit that the row refuses.",
        ],
    )


def test_the_row_passes_with_the_count_of_stage_and_implement_cases(
    stage_cases: list[StageCase], implement_cases: list[LoadedCase]
) -> None:
    """Each base commit is a full hash of a commit, so the row passes and counts both sets."""
    assert outcome(stage_cases, implement_cases, False, _resolves_everything) == (
        0,
        [
            f"roadmap-eval-commits: the base commit of each of the {len(stage_cases)} stage and "
            f"{len(implement_cases)} implement cases is a commit of the repository."
        ],
    )


@pytest.mark.parametrize(
    ("stdout", "expected"), [("true\n", True), ("false\n", False), ("", False)]
)
def test_the_shallow_answer_is_read_from_the_git_output(stdout: str, expected: bool) -> None:
    """Only the answer `true` marks a shallow clone, whatever the trailing newline."""
    assert is_shallow(stdout) is expected
