"""One result line for each attempt of a roadmap job (#4845).

Only a roadmap job that holds 80% success gets smaller caps for cost (`docs/roadmap/job-success.md`,
`docs/guidelines/agentic-jobs.md`). The counters of the jobs give no common ratio, and a metric label
cannot hold the counts of each attempt. So each job logs one line for each attempt, and a Loki
`count_over_time` query counts the lines:

    roadmap job result: job=<job> repo=<owner/repo> item=#<n> result=<result> success=<bool>
    class=<class> infra=<bool> <count>=<n> ... version=<version>

`success` is true when the result is the intended result of the job (`SUCCESS_RESULTS`), and
`infra` is true when the failure class is a cut of the infrastructure, not a fault of the job
(`INFRA_CLASSES`). The counts follow in the order that the job gives them, and the version of
devops-cli ends the line, so a query can compare two images.

A line holds no text of an issue, of a model or of a log. Each value is a number or a name of
the job, and a name that holds another character than a letter, a digit, `_`, `-` or `.` is
written as `other`. A run with no repository writes `repo=none`, and a candidate of intake that is
not an issue yet writes `item=none`.

The Service logs the line as JSON, with the line in `message` (`server/json_logs.py`). A command
that a Job pod runs writes the line, and the round lines of the attempt, to stderr as plain text
in `job_lines_to_stderr` (#5363, #5556): the log of the pod is what the command writes, and a CLI
process has no handler for `INFO` records.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from devops_cli import __version__
from devops_cli.roadmap.failure import FailureClass

logger = logging.getLogger(__name__)

LINE_PREFIX: Final = "roadmap job result:"
# The loggers of the lines of an attempt: one line for each review round and gate return, the
# progress line of each review (`round_log`), and the result line (this module).
_LINE_LOGGERS: Final[tuple[str, ...]] = ("devops_cli.roadmap.round_log", __name__)

# A name that a line may hold: an enum value, a class name or a count name of the job.
_NAME: Final = re.compile(r"[A-Za-z0-9_.-]{1,64}")
# A repository name as GitHub gives it.
_REPO: Final = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}")
_OTHER: Final = "other"
_NONE: Final = "none"


class RoadmapJob(StrEnum):
    """A roadmap job that logs one result line for each attempt. `REFINE_JUDGE` is the review of
    the proposal of refine for an item that a bot opened (`refine_judge`). `FIX_PLAN` is the step
    that repairs a plan pull request with open findings (#5061)."""

    STAGE = "stage"
    IMPLEMENT = "implement"
    REFINE = "refine"
    REFINE_JUDGE = "refine_judge"
    ALTERNATIVES = "alternatives"
    INTAKE = "intake"
    FIX_PLAN = "fix_plan"


# The intended result of each job (owner rule 2026-11-11): a stage attempt opens a plan pull
# request, an implement attempt reaches a ready pull request, a refine attempt sets the next step
# of the item, the review approves, the alternatives check writes a verdict, and intake places the
# candidate. A fix-plan attempt pushes a repair that its review finds better than the review of the
# head in the same attempt (#5213): `regated`, `dismissed`, `unchanged`, `stopped`, `failed` and
# `timeout` (#5363) repair no finding of that review, and `unreadable` writes no line. Each value
# is a member of the result enum of its job.
SUCCESS_RESULTS: Final[Mapping[RoadmapJob, frozenset[str]]] = MappingProxyType(
    {
        RoadmapJob.STAGE: frozenset({"staged"}),
        RoadmapJob.IMPLEMENT: frozenset({"ready"}),
        RoadmapJob.REFINE: frozenset({"ready", "person", "split", "blocked"}),
        RoadmapJob.REFINE_JUDGE: frozenset({"approved"}),
        RoadmapJob.ALTERNATIVES: frozenset(
            {"covers", "partly", "none", "not-applicable", "rejected", "in-use"}
        ),
        RoadmapJob.INTAKE: frozenset({"placed", "duplicate"}),
        RoadmapJob.FIX_PLAN: frozenset({"revised", "cleared"}),
    }
)


@dataclass(frozen=True)
class CountLimit:
    """A count of the result line and the most that a first-pass attempt has of it."""

    count: str
    most: int


# A first-pass attempt is a success with no fix round (owner rule 2026-11-12, #5165). These jobs
# write the counts of their fix rounds on the line, so a count over its limit is a fix round. The
# other jobs get their rule when their line gets the counts (#5168); until then their first pass is
# unknown, and the job grade `100` needs it.
FIRST_PASS_LIMITS: Final[Mapping[RoadmapJob, tuple[CountLimit, ...]]] = MappingProxyType(
    {
        RoadmapJob.STAGE: (
            CountLimit("plan_calls", 1),
            CountLimit("gate_returns", 0),
            CountLimit("verify_rounds", 1),
        ),
        RoadmapJob.IMPLEMENT: (CountLimit("repair_rounds", 0),),
        RoadmapJob.FIX_PLAN: (
            CountLimit("gate_returns", 0),
            CountLimit("verify_rounds", 1),
            CountLimit("after", 0),
        ),
    }
)

# The failure classes that a cut of the infrastructure gives: the model provider, the CI or the
# cluster, the memory of a pod, and a used budget. The ratio of the dashboard counts them as
# failures and shows their share apart. The job grade (`roadmap/job_grade.py`) leaves them out of
# its ratio, because the action of a grade is for the job.
INFRA_CLASSES: Final[frozenset[FailureClass]] = frozenset(
    {
        FailureClass.PROVIDER,
        FailureClass.CI_INFRA,
        FailureClass.OOM,
        FailureClass.LIMIT_REACHED,
    }
)


def _name(value: str) -> str:
    return value if _NAME.fullmatch(value) else _OTHER


def _item(item: int | None) -> str:
    return _NONE if item is None else f"#{item}"


def log_job_result(
    job: RoadmapJob,
    repo: str,
    item: int | None,
    result: str,
    *,
    failure: FailureClass | None = None,
    counts: Mapping[str, int] | None = None,
    names: Mapping[str, str] | None = None,
) -> None:
    """Log the one result line of an attempt of `job` on `item`. `result` is a value of the
    result enum of the job, `failure` the class of its failure, `counts` the numbers of the
    attempt, and `names` the other fixed names of the attempt, such as the code of a refused
    reply. A count below 0 is written as 0."""
    fields = [
        f"job={job.value}",
        f"repo={repo if _REPO.fullmatch(repo) else _NONE}",
        f"item={_item(item)}",
        f"result={_name(result)}",
        f"success={str(result in SUCCESS_RESULTS[job]).lower()}",
        f"class={failure.value if failure else _NONE}",
        f"infra={str(failure in INFRA_CLASSES).lower()}",
    ]
    fields += [f"{_name(key)}={max(int(value), 0)}" for key, value in (counts or {}).items()]
    fields += [f"{_name(key)}={_name(value)}" for key, value in (names or {}).items()]
    fields.append(f"version={__version__}")
    logger.info("%s %s", LINE_PREFIX, " ".join(fields))


@contextmanager
def job_lines_to_stderr() -> Iterator[None]:
    """Write the `INFO` lines of the round log and the result lines to stderr as plain text while
    the block runs. The lines hold counts and names, and no text of a model or of an issue."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    loggers = [logging.getLogger(name) for name in _LINE_LOGGERS]
    levels = [each.level for each in loggers]
    for each in loggers:
        each.addHandler(handler)
        each.setLevel(logging.INFO)
    try:
        yield
    finally:
        for each, level in zip(loggers, levels, strict=True):
            each.removeHandler(handler)
            each.setLevel(level)


__all__ = [
    "FIRST_PASS_LIMITS",
    "INFRA_CLASSES",
    "LINE_PREFIX",
    "SUCCESS_RESULTS",
    "CountLimit",
    "RoadmapJob",
    "job_lines_to_stderr",
    "log_job_result",
]
