"""The size of a runner Job, chosen from its plan (#3193).

A Job that implements a small item does not need the memory and the CPU of a Job that changes forty
files. The Service counts the files that `tasks.md` of the plan names, and takes the row of
`RUNNER_SIZES` for that count. The CPU of a row is the request, the limit and the worker count of
`pytest-xdist`, which counts the CPUs of the node and not of the pod (#2806). The memory of a row is
the request and the limit (#7422). The scheduler places a pod by its request only, and the kernel
cannot take memory back from a process. So a Job with a limit above its request can go to a node
that cannot hold the limit, and then takes memory from the other pods of the node.

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
    """One row of the table: the CPU and the memory of a Job, each the request and the limit, and
    the measurement that sets the memory. `peak_bytes` is at most 80 % of the memory."""

    max_files: int | None
    cpu: str
    memory: str
    sample: str
    peak_bytes: int

    @property
    def env(self) -> dict[str, str]:
        """The worker count of the test runner: the CPU limit of the same Job."""
        return {WORKERS_VARIABLE: self.cpu}

    def resources(self) -> dict[str, dict[str, str]]:
        """The requests and limits that replace those of the template: each limit equals its
        request."""
        values = {"cpu": self.cpu, "memory": self.memory}
        return {"requests": dict(values), "limits": dict(values)}


# The peaks are the highest working set of the container that ran the step, in the runner Jobs of
# each row in the 14 days to 2026-11-27, read from Prometheus (#7422). Each Job then had a memory
# limit of 16Gi, so no peak was cut by a limit. The two peaks are of Jobs with one container,
# which also ran `prepare` and `publish`; the `agent` container of a Job on the three containers
# peaked at 2.10 GiB in the small row and at 4.54 GiB in the large row. The peak is at most 80 % of
# the memory of its row, the room of T1 in docs/guidelines/kubernetes.md. A third row needs a third
# measurement.
RUNNER_SIZES: Final[tuple[RunnerSize, ...]] = (
    RunnerSize(
        max_files=SMALL_PLAN_MAX_FILES,
        cpu="1",
        memory="5Gi",
        sample="the 42 runner Jobs of the small row in the 14 days to 2026-11-27 (#7422)",
        peak_bytes=int(4.08 * _GB),
    ),
    RunnerSize(
        max_files=None,
        cpu="4",
        memory="11Gi",
        sample="the 117 runner Jobs of the large row in the 14 days to 2026-11-27 (#7422)",
        peak_bytes=int(8.65 * _GB),
    ),
)


def plan_file_count(tasks_md: str) -> int:
    """The distinct file paths that the code spans of `tasks_md` name."""
    return len({span for span in _CODE_SPAN.findall(tasks_md) if _PATH.fullmatch(span)})


def runner_size(files: int) -> RunnerSize:
    """The row of the table for a plan that names `files` files."""
    return next(row for row in RUNNER_SIZES if row.max_files is None or files <= row.max_files)
