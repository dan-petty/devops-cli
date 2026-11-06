"""The size of a runner Job, chosen from its plan (#3193).

A Job that implements a small item does not need the memory and the CPU of a Job that changes forty
files. The Service counts the files that `tasks.md` of the plan names, and takes the row of
`RUNNER_SIZES` for that count. The CPU of a row is the request, the limit and the worker count of
`pytest-xdist`, which counts the CPUs of the node and not of the pod (#2806). The memory limit is
not in the table: it is the setting `roadmap.implement.max_memory_limit`, so one limit protects the
node for every row.

The admission policy `roadmap-service-jobs` admits the rows of this table and no other size
(`k8s/devops/roadmap-service/admissionpolicy.yaml`). A gate check holds the two equal. A person who
changes a row changes the policy in the same pull request.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# The Job variable that bounds the workers of the test runner to the CPU limit of the pod.
WORKERS_VARIABLE: Final[str] = "PYTEST_XDIST_AUTO_NUM_WORKERS"
# A plan of at most this many files takes the small row; a larger plan takes the large row.
SMALL_PLAN_MAX_FILES: Final[int] = 10

_GB: Final[int] = 10**9
# A path in a code span: a name with a `/`, or a file at the root with a suffix that the plans use.
# A command has a space, and a setting or a module has dots and no `/`, so neither matches.
_PATH: Final[re.Pattern[str]] = re.compile(
    r"[\w.-]+(?:/[\w.-]+)+|[\w-]+\.(?:md|py|yaml|yml|toml|json|txt|cfg|ini|sh|lock)"
)
_CODE_SPAN: Final[re.Pattern[str]] = re.compile(r"`([^`\n]+)`")


@dataclass(frozen=True)
class RunnerSize:
    """One row of the table: the CPU (request and limit) and the memory request of a Job, and the
    measurement that sets the memory request. The memory request is above `peak_bytes`."""

    max_files: int | None
    cpu: str
    memory: str
    sample: str
    peak_bytes: int

    @property
    def env(self) -> dict[str, str]:
        """The worker count of the test runner: the CPU limit of the same Job."""
        return {WORKERS_VARIABLE: self.cpu}

    def resources(self, memory_limit: str) -> dict[str, dict[str, str]]:
        """The requests and limits that replace those of the template. The CPU request equals the
        CPU limit, and the memory limit is `memory_limit`."""
        return {
            "requests": {"cpu": self.cpu, "memory": self.memory},
            "limits": {"cpu": self.cpu, "memory": memory_limit},
        }


# The peaks are the measured ones of the runner Jobs (#2806): the normal peak of the 10 Jobs that
# did not run out of memory, and the peak that the Job reached before the kernel killed it at its
# 4 Gi cap, which was still growing. A third row needs a third measurement.
RUNNER_SIZES: Final[tuple[RunnerSize, ...]] = (
    RunnerSize(
        max_files=SMALL_PLAN_MAX_FILES,
        cpu="1",
        memory="2Gi",
        sample="the 10 runner Jobs of #2806 that did not run out of memory",
        peak_bytes=int(1.24 * _GB),
    ),
    RunnerSize(
        max_files=None,
        cpu="4",
        memory="6Gi",
        sample="the runner Job of #2806 that the kernel killed at its 4 Gi cap",
        peak_bytes=int(4.13 * _GB),
    ),
)

# The memory limit may not be below the largest request, or the API refuses the Job.
MIN_MEMORY_LIMIT_GI: Final[int] = max(int(row.memory.removesuffix("Gi")) for row in RUNNER_SIZES)


def plan_file_count(tasks_md: str) -> int:
    """The distinct file paths that the code spans of `tasks_md` name."""
    return len({span for span in _CODE_SPAN.findall(tasks_md) if _PATH.fullmatch(span)})


def runner_size(files: int) -> RunnerSize:
    """The row of the table for a plan that names `files` files."""
    return next(row for row in RUNNER_SIZES if row.max_files is None or files <= row.max_files)
