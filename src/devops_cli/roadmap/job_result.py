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
in `job_lines_to_stderr` (#5363, #5556). The OpenTelemetry logging handler sends `INFO` records
of this module to the collector (#5169).
"""

from __future__ import annotations

import logging
import re
import sys
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from devops_cli import __version__
from devops_cli.roadmap.failure import FailureClass

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
    that repairs a plan pull request with open findings (#5061). `FIX_CHECKS` is the fix-checks Job
    that the watch row starts, which the Service reports when it ends (#5027). `REVIEW` is the step
    that gives a bot pull request its verdict (#5969)."""

    STAGE = "stage"
    IMPLEMENT = "implement"
    REFINE = "refine"
    REFINE_JUDGE = "refine_judge"
    ALTERNATIVES = "alternatives"
    INTAKE = "intake"
    FIX_PLAN = "fix_plan"
    FIX_CHECKS = "fix_checks"
    RETITLE = "retitle"
    REVIEW = "review"


# The intended result of each job (owner rule 2026-11-11): a stage attempt opens a plan pull
# request, an implement attempt opens or updates its draft pull request with the final title and
# body (#6559: the watch row and the fix-checks Jobs take the draft to ready), a refine attempt
# sets the next step of the item, the review approves, the alternatives check writes a verdict, intake places the
# candidate, and retitle shortens or keeps the title. A fix-plan attempt pushes a repair that its
# review finds better than the review of the head in the same attempt (#5213): `regated`, `dismissed`,
# `unchanged`, `stopped`, `failed` and `timeout` (#5363) repair no finding of that review, and
# `unreadable` writes no line. A fix-checks Job pushes a repair or marks its repaired draft ready
# (#5027). A review attempt gives the pull request one verdict (#5969); an attempt that waits for
# its checks, or that a guard skips, writes no line. Each value is a member of the result enum of
# its job.
SUCCESS_RESULTS: Final[Mapping[RoadmapJob, frozenset[str]]] = MappingProxyType(
    {
        RoadmapJob.STAGE: frozenset({"staged"}),
        RoadmapJob.IMPLEMENT: frozenset({"drafted"}),
        # Each next step of refine that is a wait is a success: `alternatives` waits on the
        # verdict of the alternatives row (#2951), and `edit` on a body edit, because the body
        # stops the design. `retry` and `failed` are failures of the job (#6037).
        RoadmapJob.REFINE: frozenset(
            {"ready", "person", "split", "blocked", "alternatives", "edit"}
        ),
        RoadmapJob.REFINE_JUDGE: frozenset({"approved"}),
        RoadmapJob.ALTERNATIVES: frozenset(
            {"covers", "partly", "none", "not-applicable", "rejected", "in-use"}
        ),
        RoadmapJob.INTAKE: frozenset({"placed", "duplicate"}),
        RoadmapJob.FIX_PLAN: frozenset({"revised", "cleared"}),
        RoadmapJob.FIX_CHECKS: frozenset({"repaired", "rebased", "ready"}),
        RoadmapJob.RETITLE: frozenset({"retitled", "kept"}),
        RoadmapJob.REVIEW: frozenset({"judged"}),
    }
)


@dataclass(frozen=True)
class CountLimit:
    """A count of the result line and the most that a first-pass attempt has of it."""

    count: str
    most: int


# A first-pass attempt is a success with no fix round (owner rule 2026-11-12, #5165, #5168). These
# jobs write the counts of their fix rounds on the line, so a count over its limit is a fix round.
FIRST_PASS: Final[Mapping[RoadmapJob, tuple[CountLimit, ...]]] = MappingProxyType(
    {
        RoadmapJob.STAGE: (
            CountLimit("plan_calls", 1),
            CountLimit("gate_returns", 0),
            CountLimit("verify_rounds", 1),
        ),
        RoadmapJob.IMPLEMENT: (
            CountLimit("repair_rounds", 0),
            CountLimit("extensions", 0),
        ),
        RoadmapJob.FIX_PLAN: (
            CountLimit("gate_returns", 0),
            CountLimit("verify_rounds", 1),
            CountLimit("after", 0),
        ),
        RoadmapJob.REFINE: (CountLimit("tries", 1),),
        RoadmapJob.REFINE_JUDGE: (
            CountLimit("round", 1),
            CountLimit("findings", 0),
        ),
        RoadmapJob.ALTERNATIVES: (CountLimit("returns", 0),),
        RoadmapJob.INTAKE: (CountLimit("fallbacks", 0),),
        RoadmapJob.RETITLE: (CountLimit("model_calls", 1),),
        RoadmapJob.FIX_CHECKS: (CountLimit("attempt", 1),),
    }
)

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


def is_first_pass(job: RoadmapJob, result: str, counts: Mapping[str, int]) -> bool:
    """Whether an attempt succeeded with no fix round (owner rule 2026-11-12, #5165, #5168)."""
    if result not in SUCCESS_RESULTS.get(job, frozenset()):
        return False
    if job == RoadmapJob.STAGE and "plan_calls" not in counts:
        return False
    limits = FIRST_PASS.get(job, ())
    for limit in limits:
        if counts.get(limit.count, 0) > limit.most:
            return False
    return True


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


@dataclass
class AttemptContext:
    """Tallies efficiency metrics across an attempt of a roadmap job (#5168)."""

    start_time: float
    model_calls: int = 0
    tokens: int = 0
    cost_usd_micros: int = 0
    gh_requests: int = 0

    @property
    def seconds(self) -> int:
        return max(round(time.perf_counter() - self.start_time), 0)

    def record_model(self, tokens: int, cost_usd: float) -> None:
        self.model_calls += 1
        self.tokens += max(int(tokens), 0)
        self.cost_usd_micros += max(round(cost_usd * 1_000_000), 0)

    def record_gh(self) -> None:
        self.gh_requests += 1

    def counts(self) -> dict[str, int]:
        return {
            "model_calls": self.model_calls,
            "tokens": self.tokens,
            "seconds": self.seconds,
            "cost_usd_micros": self.cost_usd_micros,
            "gh_requests": self.gh_requests,
        }


_ATTEMPT_CONTEXT: ContextVar[AttemptContext | None] = ContextVar(
    "roadmap_attempt_context", default=None
)


@contextmanager
def attempt_context() -> Iterator[AttemptContext]:
    """Open an attempt context that tallies model calls, tokens, cost, and GitHub requests."""
    ctx = AttemptContext(start_time=time.perf_counter())
    token = _ATTEMPT_CONTEXT.set(ctx)
    try:
        yield ctx
    finally:
        _ATTEMPT_CONTEXT.reset(token)


def record_attempt_ai(tokens: int, cost_usd: float) -> None:
    """Add one model call to the active attempt context, if one is open."""
    ctx = _ATTEMPT_CONTEXT.get()
    if ctx is not None:
        ctx.record_model(tokens, cost_usd)


def record_attempt_gh() -> None:
    """Add one GitHub request to the active attempt context, if one is open."""
    ctx = _ATTEMPT_CONTEXT.get()
    if ctx is not None:
        ctx.record_gh()


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
    all_counts: dict[str, int] = {}
    ctx = _ATTEMPT_CONTEXT.get()
    if ctx is not None:
        all_counts.update(ctx.counts())
    if counts:
        all_counts.update(counts)

    success = result in SUCCESS_RESULTS[job]
    first_pass = is_first_pass(job, result, all_counts)

    fields = [
        f"job={job.value}",
        f"repo={repo if _REPO.fullmatch(repo) else _NONE}",
        f"item={_item(item)}",
        f"result={_name(result)}",
        f"success={str(success).lower()}",
        f"class={failure.value if failure else _NONE}",
        f"infra={str(failure in INFRA_CLASSES).lower()}",
        f"first_pass={str(first_pass).lower()}",
    ]
    fields += [f"{_name(key)}={max(int(value), 0)}" for key, value in all_counts.items()]
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
    "FIRST_PASS",
    "FIRST_PASS_LIMITS",
    "INFRA_CLASSES",
    "LINE_PREFIX",
    "SUCCESS_RESULTS",
    "AttemptContext",
    "CountLimit",
    "RoadmapJob",
    "attempt_context",
    "is_first_pass",
    "job_lines_to_stderr",
    "log_job_result",
    "record_attempt_ai",
    "record_attempt_gh",
]
