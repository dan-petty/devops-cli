"""The base commit of each golden stage eval case: the `roadmap-stage-eval-commits` row of
`devops ci` (#4449).

A pytest test used to start a real git and skip on a shallow clone, which `docs/TESTING.md`
forbids, so the check of the base commits is a row of the gate. `git rev-parse
--is-shallow-repository` gives the shallow answer, and `git cat-file -e <sha>^{commit}` resolves
each base commit. A case that no merge made holds `NO_COMMIT`, and its notes say that it reads no
commit (#3688).

The verdict is a pure function of the cases, the shallow answer and a `resolves` that tells
whether a hash names a commit, so a test gives it canned answers and starts no git.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from typing import Final

from devops_cli.roadmap.stage.stage_eval_cases import (
    CASES_DIRECTORY,
    NO_COMMIT,
    StageCase,
    load_cases,
)
from tests.support.paths import REPO_ROOT

_ROW: Final[str] = "roadmap-stage-eval-commits"
_READS_NO_COMMIT: Final[str] = "reads no commit"
FULL_HASH: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{40}")
_GIT_TIMEOUT_SECONDS: Final[int] = 60
_ERROR_DETAIL_CHARACTERS: Final[int] = 256


def is_shallow(stdout: str) -> bool:
    """Whether `git rev-parse --is-shallow-repository` answered a shallow clone."""
    return stdout.strip() == "true"


def bad_base_commits(cases: Sequence[StageCase], resolves: Callable[[str], bool]) -> list[str]:
    """The line of each case whose base commit is not a full hash that `resolves` accepts, or is
    `NO_COMMIT` with no note that says that it reads no commit."""
    found: list[str] = []
    for case in cases:
        if case.base_commit == NO_COMMIT:
            if not any(_READS_NO_COMMIT in note for note in case.notes):
                found.append(
                    f"{case.name}: its base commit is NO_COMMIT and no note says that it "
                    f"{_READS_NO_COMMIT}"
                )
        elif not (FULL_HASH.fullmatch(case.base_commit) and resolves(case.base_commit)):
            found.append(f"{case.name}: {case.base_commit} is not a commit of the repository")
    return found


def outcome(
    cases: Sequence[StageCase], shallow: bool, resolves: Callable[[str], bool]
) -> tuple[int, list[str]]:
    """The exit status of the row and the lines that it prints, for the shallow answer of git and
    the `resolves` that tells whether a hash names a commit."""
    if shallow:
        return 1, [
            f"{_ROW}: the shallow clone lacks the history that the golden cases need "
            f"({len(cases)} cases). Fetch it with `git fetch --unshallow`."
        ]
    found = bad_base_commits(cases, resolves)
    if not found:
        return 0, [
            f"{_ROW}: the base commit of each of the {len(cases)} cases is a commit of the "
            "repository."
        ]
    return 1, [
        *(f"{_ROW}: {finding}" for finding in found),
        f"{_ROW}: {len(found)} of {len(cases)} cases name a base commit that the row refuses.",
    ]


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    """Run git in the repository and give its result, with a bound of 60 s."""
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        check=False,
        timeout=_GIT_TIMEOUT_SECONDS,
    )


def main(argv: list[str] | None = None) -> int:
    """Read the shallow answer and each base commit with git, print the findings, and return 1
    when there is one."""
    cases = load_cases(REPO_ROOT / CASES_DIRECTORY)
    shallow = _git("rev-parse", "--is-shallow-repository")
    if shallow.returncode:
        detail = shallow.stderr.decode("utf-8", "replace")[:_ERROR_DETAIL_CHARACTERS]
        print(f"{_ROW}: git rev-parse --is-shallow-repository failed: {detail}", file=sys.stderr)
        return 1

    def resolves(sha: str) -> bool:
        return _git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0

    status, lines = outcome(cases, is_shallow(shallow.stdout.decode("utf-8", "replace")), resolves)
    for line in lines:
        print(line, file=sys.stderr if status else sys.stdout)
    return status
