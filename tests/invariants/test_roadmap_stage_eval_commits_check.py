"""The base commit of each golden stage eval case: the `roadmap-stage-eval-commits` row of
`devops ci` (#4449).

git gives the shallow answer and resolves each base commit, so these cases give the row canned
answers and no test starts git. The real set gives the count of cases and each note.
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.stage.stage_eval_cases import (
    CASES_DIRECTORY,
    NO_COMMIT,
    StageCase,
    load_cases,
)
from tests.gate.roadmap_stage_eval_commits import is_shallow, outcome
from tests.support.paths import REPO_ROOT


@pytest.fixture(scope="module")
def cases() -> list[StageCase]:
    return load_cases(REPO_ROOT / CASES_DIRECTORY)


def _resolves_everything(sha: str) -> bool:
    return True


def _resolves_nothing(sha: str) -> bool:
    return False


def test_the_row_fails_on_a_shallow_clone(cases: list[StageCase]) -> None:
    """A shallow clone lacks the history that the cases need, so the row says so and fails."""
    assert outcome(cases, True, _resolves_everything) == (
        1,
        [
            "roadmap-stage-eval-commits: the shallow clone lacks the history that the golden "
            f"cases need ({len(cases)} cases). Fetch it with `git fetch --unshallow`."
        ],
    )


def test_the_row_names_each_base_commit_that_git_cannot_resolve(
    cases: list[StageCase],
) -> None:
    """A base commit that git does not resolve gives a line with the case name and the hash."""
    committed = [case for case in cases if case.base_commit != NO_COMMIT]

    status, lines = outcome(cases, False, _resolves_nothing)

    assert (status, lines) == (
        1,
        [
            *(
                f"roadmap-stage-eval-commits: {case.name}: {case.base_commit} is not a commit of "
                "the repository"
                for case in committed
            ),
            f"roadmap-stage-eval-commits: {len(committed)} of {len(cases)} cases name a base "
            "commit that the row refuses.",
        ],
    )


def test_the_row_names_a_case_that_reads_no_commit_with_no_note(
    cases: list[StageCase],
) -> None:
    """A case with NO_COMMIT passes only with a note that says that it reads no commit."""
    case = cases[0].model_copy(update={"base_commit": NO_COMMIT, "notes": ()})

    assert outcome([case], False, _resolves_everything) == (
        1,
        [
            f"roadmap-stage-eval-commits: {case.name}: its base commit is NO_COMMIT and no note "
            "says that it reads no commit",
            "roadmap-stage-eval-commits: 1 of 1 cases name a base commit that the row refuses.",
        ],
    )


def test_the_row_passes_with_the_count_of_cases(cases: list[StageCase]) -> None:
    """Each base commit is a full hash of a commit, so the row passes and counts the cases."""
    assert outcome(cases, False, _resolves_everything) == (
        0,
        [
            f"roadmap-stage-eval-commits: the base commit of each of the {len(cases)} cases is a "
            "commit of the repository."
        ],
    )


@pytest.mark.parametrize(
    ("stdout", "expected"), [("true\n", True), ("false\n", False), ("", False)]
)
def test_the_shallow_answer_is_read_from_the_git_output(stdout: str, expected: bool) -> None:
    """Only the answer `true` marks a shallow clone, whatever the trailing newline."""
    assert is_shallow(stdout) is expected
