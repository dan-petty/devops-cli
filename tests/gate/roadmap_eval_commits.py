"""The base commit of each golden eval case: the `roadmap-eval-commits` row of `devops ci`
(#4449, #5516).

Both golden sets record a base commit on this repository, so each must resolve with `git cat-file`,
unless a stage case names `NO_COMMIT` with a note that says it reads no commit.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from typing import Final

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
from tests.support.paths import REPO_ROOT

_ROW: Final[str] = "roadmap-eval-commits"
_READS_NO_COMMIT: Final[str] = "reads no commit"
FULL_HASH: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{40}")
_GIT_TIMEOUT_SECONDS: Final[int] = 60


def is_shallow(stdout: str) -> bool:
    """Whether `git rev-parse --is-shallow-repository` reported a shallow clone."""
    return stdout.strip() == "true"


def bad_base_commits(
    stage_cases: Sequence[StageCase],
    implement_cases: Sequence[LoadedCase],
    resolves: Callable[[str], bool],
) -> list[str]:
    """Each finding for a stage or implement case whose base commit cannot be used."""
    findings: list[str] = []
    for case in stage_cases:
        if case.base_commit == NO_COMMIT:
            if not any(_READS_NO_COMMIT in note.lower() for note in case.notes):
                findings.append(
                    f"{_ROW}: {case.name}: its base commit is NO_COMMIT and no note says "
                    "that it reads no commit"
                )
        elif not (FULL_HASH.fullmatch(case.base_commit) and resolves(case.base_commit)):
            findings.append(
                f"{_ROW}: {case.name}: {case.base_commit} is not a commit of the repository"
            )
    for loaded in implement_cases:
        base = loaded.case.base
        if not (FULL_HASH.fullmatch(base) and resolves(base)):
            findings.append(f"{_ROW}: {loaded.name}: {base} is not a commit of the repository")
    return findings


def outcome(
    stage_cases: Sequence[StageCase],
    implement_cases: Sequence[LoadedCase],
    shallow: bool,
    resolves: Callable[[str], bool],
) -> tuple[int, list[str]]:
    """The exit status of the row and the lines it prints for both golden sets."""
    total = len(stage_cases) + len(implement_cases)
    if shallow:
        return 1, [
            f"{_ROW}: the shallow clone lacks the history that the golden cases need "
            f"({total} cases). Fetch it with `git fetch --unshallow`."
        ]
    findings = bad_base_commits(stage_cases, implement_cases, resolves)
    if findings:
        return 1, [
            *findings,
            f"{_ROW}: {len(findings)} of {total} cases name a base commit that the row refuses.",
        ]
    return 0, [
        f"{_ROW}: the base commit of each of the {len(stage_cases)} stage and "
        f"{len(implement_cases)} implement cases is a commit of the repository."
    ]


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    """Run one git read command in `REPO_ROOT` without raising on nonzero status."""
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=_GIT_TIMEOUT_SECONDS,
    )


def main(argv: list[str] | None = None) -> int:
    """Check the base commit of every golden stage and implement eval case."""
    del argv
    stage_cases = load_stage_cases(REPO_ROOT / CASES_DIRECTORY)
    implement_cases = load_implement_cases(REPO_ROOT / CONST_ROADMAP_EVAL_IMPLEMENT_FIXTURES)
    shallow = is_shallow(_git("rev-parse", "--is-shallow-repository").stdout)
    status, lines = outcome(
        stage_cases,
        implement_cases,
        shallow,
        lambda sha: _git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0,
    )
    stream = sys.stderr if status else sys.stdout
    for line in lines:
        print(line, file=stream)
    return status
