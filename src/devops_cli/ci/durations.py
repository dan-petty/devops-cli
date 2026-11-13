"""The recorded seconds of each test module, which balance the test shards of CI (#5247).

The split of the test shards by lines of test code put a short module with slow tests in a shard
that then took longest, and each change of the tree moved modules between shards (#4250). Each
shard of `ci.yml` uploads a JUnit XML report with the time of each of its tests, in the artifact
`coverage-shard-<n>` (#4673). `record_durations` reads these reports of the last runs of the test
check on a branch, adds the seconds of the tests of each module, and takes the mean of each module
over the runs that ran it. `write_durations` writes the means to `CONST_CI_TEST_DURATIONS_PATH`,
which `core.test_selection.shard_test_files` reads. gh downloads and unpacks the artifacts.
"""

from __future__ import annotations

import json
import math
import tempfile
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final

from devops_cli.ci.fail_to_pass import parse_junit_xml
from devops_cli.config.constants import (
    CONST_CI_SHARD_JUNIT_PATH,
    CONST_CI_TEST_DURATIONS_PATH,
    CONST_PYTHON_FILE_SUFFIX,
)
from devops_cli.github.rate_limiter import run_gh

if TYPE_CHECKING:
    from devops_cli.ci.fail_to_pass import TestCaseOutcome
    from devops_cli.github.client import GitHubClient

# The artifact of each test shard of `ci.yml` is `coverage-shard-<n>`: it holds the coverage data
# and the JUnit XML report of the shard.
SHARD_ARTIFACT_PREFIX: Final[str] = "coverage-shard-"
_REPORT_NAME: Final[str] = PurePosixPath(CONST_CI_SHARD_JUNIT_PATH).name
# The artifacts of one run hold about 15 MB.
_DOWNLOAD_TIMEOUT_SECONDS: Final[float] = 300.0
# The record keeps tenths of a second: a finer value only changes more lines at each refresh.
_DECIMALS: Final[int] = 1


@dataclass(frozen=True)
class DurationsRecord:
    """The runs whose shard reports were read, and the mean seconds of each test module."""

    runs: tuple[int, ...]
    durations: dict[str, float]


def module_of(classname: str, modules: Collection[str]) -> str | None:
    """The test module of the JUnit `classname` of a test, as a path of `modules`; None when no
    module of `modules` holds it. Pytest writes the path of the module with dots for slashes and
    no suffix, then the class of the test when it has one (`tests.a.test_x.TestCase`)."""
    parts = classname.split(".")
    for end in range(len(parts), 0, -1):
        path = "/".join(parts[:end]) + CONST_PYTHON_FILE_SUFFIX
        if path in modules:
            return path
    return None


def module_seconds(
    outcomes: Iterable[TestCaseOutcome], modules: Collection[str]
) -> dict[str, float]:
    """The sum of the seconds of the tests of each module of `modules` in `outcomes`. A test of a
    module that `modules` does not hold counts nowhere."""
    found: dict[str, list[float]] = {}
    for outcome in outcomes:
        module = module_of(outcome.classname, modules)
        if module is not None:
            found.setdefault(module, []).append(outcome.seconds)
    return {module: math.fsum(seconds) for module, seconds in found.items()}


def mean_durations(runs: Sequence[Mapping[str, float]]) -> dict[str, float]:
    """The mean seconds of each module over the runs that ran it, in tenths of a second and in
    the order of the paths."""
    found: dict[str, list[float]] = {}
    for run in runs:
        for module, seconds in run.items():
            found.setdefault(module, []).append(seconds)
    return {
        module: round(math.fsum(seconds) / len(seconds), _DECIMALS)
        for module, seconds in sorted(found.items())
    }


def write_durations(root: Path, durations: Mapping[str, float]) -> Path:
    """Write `durations` to `CONST_CI_TEST_DURATIONS_PATH` under `root`, one module a line in the
    order of the paths, and return the path."""
    path = root / CONST_CI_TEST_DURATIONS_PATH
    text = json.dumps(dict(sorted(durations.items())), indent=2)
    path.write_text(f"{text}\n", encoding="utf-8")
    return path


def download_shard_reports(repo: str, run_id: int, directory: Path) -> list[Path]:
    """Download the shard artifacts of the run `run_id` of `repo` into `directory` with
    `gh run download`, which unpacks each one into a folder of its name; return the paths of the
    JUnit XML reports that they hold, in order. A failed download raises."""
    run_gh(
        [
            "run",
            "download",
            str(run_id),
            "--repo",
            repo,
            "--dir",
            str(directory),
            "--pattern",
            f"{SHARD_ARTIFACT_PREFIX}*",
        ],
        check=True,
        timeout=_DOWNLOAD_TIMEOUT_SECONDS,
    )
    return sorted(directory.glob(f"{SHARD_ARTIFACT_PREFIX}*/{_REPORT_NAME}"))


def record_durations(
    client: GitHubClient,
    repo: str,
    *,
    workflow: str,
    branch: str,
    job: str,
    runs: int,
    modules: Collection[str],
) -> DurationsRecord:
    """The mean seconds of each module of `modules` in the shard reports of the last `runs` push
    runs of `workflow` on `branch` where the check `job` ran to an end. A run whose artifacts
    GitHub no longer holds gives no report and is left out."""
    per_run: list[dict[str, float]] = []
    read: list[int] = []
    for run in client.get_job_run_times(
        repo, workflow=workflow, branch=branch, job=job, count=runs
    ):
        names = client.get_run_artifact_names(repo, run.run_id)
        if not any(name.startswith(SHARD_ARTIFACT_PREFIX) for name in names):
            continue
        with tempfile.TemporaryDirectory(prefix="devops-durations-") as folder:
            reports = download_shard_reports(repo, run.run_id, Path(folder))
            outcomes = [
                outcome
                for report in reports
                for outcome in parse_junit_xml(report.read_text(encoding="utf-8"))
            ]
        per_run.append(module_seconds(outcomes, modules))
        read.append(run.run_id)
    return DurationsRecord(runs=tuple(read), durations=mean_durations(per_run))
