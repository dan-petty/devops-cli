"""The deadline of a runner Job follows its progress (#3063).

The runner Job starts with a short deadline, `roadmap.implement.deadline_extension_seconds`. The
Service moves it in each round of the `implement` row, for each Job that it made and that has not
ended. The runner pod has no Kubernetes token, so it cannot move its own deadline.

**Progress.** The runner writes one line to the Job log for each tool call, and a Job that waits
writes none. The Service reads the last `CONST_ROADMAP_IMPLEMENT_DEADLINE_LOG_LINES` lines and
compares their digest with the digest it kept on the Job. A digest that differs is progress. An
empty log, or a log that the API refuses, is no signal.

**Extension.** On progress the deadline becomes the seconds since the Job started plus the
extension step, cut to the ceiling `roadmap.implement.deadline_ceiling_seconds`. It never goes
down on progress. The extension is also the limit of a Service that is down: the Job ends at most
one extension after the last progress that the Service saw.

**Stall.** A log that stayed the same for `roadmap.implement.deadline_stall_seconds` is a stall.
The Service sets the deadline to the seconds since the Job started, so the Job controller ends the
Job by its deadline at once. It marks the Job, and the report of the Job says so.

**State.** The state is on the Job, as annotations: the digest, the time (epoch seconds) of the
last progress that the Service saw, and the seconds of silence at a stall. A Job without the
second annotation is not a Job of the Service, such as a Job that `devops k8s run-job` makes, and
it keeps its deadline. A restart of the Service loses nothing.

Each change of the deadline is a span `implement.deadline` and a log line.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_ANNOTATION_PROGRESS,
    CONST_ROADMAP_IMPLEMENT_ANNOTATION_PROGRESS_AT,
    CONST_ROADMAP_IMPLEMENT_ANNOTATION_STALLED,
    CONST_ROADMAP_IMPLEMENT_DEADLINE_LOG_LINES,
)
from devops_cli.config.settings import RoadmapImplementConfig, load_settings
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.k8s.cluster_job_api import ClusterJob, ClusterJobs, JobState
from devops_cli.lang import MESSAGES
from devops_cli.telemetry.tracer import get_tracer

logger = logging.getLogger(__name__)

REASON_PROGRESS = "progress"
REASON_CEILING = "progress, ceiling"
REASON_STALL = "stall"


@dataclass(frozen=True)
class DeadlineChange:
    """A deadline that the Service moved: the Job, the deadline before and after, in seconds, and
    why."""

    job: str
    previous: int
    seconds: int
    reason: str


def is_managed(job: ClusterJob) -> bool:
    """Whether the Service made the Job: it carries the time of its last seen progress."""
    return CONST_ROADMAP_IMPLEMENT_ANNOTATION_PROGRESS_AT in job.annotations


def _digest(api: ClusterJobs, name: str) -> str:
    """The digest of the tail of the log of Job `name`, or empty when the log is empty or the API
    refuses it: a pod that has not started has no log, and that is no progress."""
    try:
        tail = api.log_tail(name, CONST_ROADMAP_IMPLEMENT_DEADLINE_LOG_LINES)
    except ClusterJobError:
        return ""
    return hashlib.sha256(tail.encode("utf-8")).hexdigest() if tail.strip() else ""


def _epoch(text: str | None, default: float) -> float:
    """The seconds in annotation `text`, or `default` when it holds none: an annotation that a
    person changed restarts the clock of the stall and does not stop the round."""
    try:
        return float(text) if text is not None else default
    except ValueError:
        return default


def _record(change: DeadlineChange, silence: int | None = None) -> None:
    """Write the span and the log line of a change of the deadline."""
    with get_tracer().span(
        "implement.deadline",
        attributes={
            "job": change.job,
            "deadline.previous_seconds": change.previous,
            "deadline.seconds": change.seconds,
            "reason": change.reason,
        },
    ):
        texts = MESSAGES.roadmap
        if silence is None:
            logger.info(
                texts.implement_deadline_extended.format(
                    job=change.job,
                    previous=change.previous,
                    seconds=change.seconds,
                    reason=change.reason,
                )
            )
        else:
            logger.info(
                texts.implement_deadline_stalled.format(
                    job=change.job, silence=silence, seconds=change.seconds
                )
            )


def _progress(
    api: ClusterJobs,
    job: ClusterJob,
    deadline: int,
    elapsed: int,
    digest: str,
    now: float,
    limits: RoadmapImplementConfig,
) -> DeadlineChange | None:
    """Keep the digest and the time of the progress on the Job, and move the deadline ahead of the
    work. Return the change, or None when the deadline stays."""
    target = elapsed + limits.deadline_extension_seconds
    wanted = max(deadline, min(limits.deadline_ceiling_seconds, target))
    marks = {
        CONST_ROADMAP_IMPLEMENT_ANNOTATION_PROGRESS: digest,
        CONST_ROADMAP_IMPLEMENT_ANNOTATION_PROGRESS_AT: str(int(now)),
    }
    api.patch_job(job.name, deadline=wanted if wanted != deadline else None, annotations=marks)
    if wanted == deadline:
        return None
    reason = REASON_CEILING if target > limits.deadline_ceiling_seconds else REASON_PROGRESS
    return DeadlineChange(job.name, deadline, wanted, reason)


def _stall(
    api: ClusterJobs, job: ClusterJob, deadline: int, elapsed: int, silence: int
) -> DeadlineChange:
    """End the Job by its deadline: set the deadline to the seconds since the start, and mark the
    Job with the seconds of silence."""
    ended = min(deadline, elapsed)
    api.patch_job(
        job.name,
        deadline=ended,
        annotations={CONST_ROADMAP_IMPLEMENT_ANNOTATION_STALLED: str(silence)},
    )
    return DeadlineChange(job.name, deadline, ended, REASON_STALL)


def _watch(
    api: ClusterJobs, job: ClusterJob, deadline: int, started: datetime, moment: float
) -> DeadlineChange | None:
    """Read the log of one Job and extend its deadline, end the Job, or leave it. Return the
    change, or None."""
    limits = load_settings().roadmap.implement
    elapsed = max(1, math.ceil(moment - started.timestamp()))
    seen = job.annotations.get(CONST_ROADMAP_IMPLEMENT_ANNOTATION_PROGRESS, "")
    last = _epoch(job.annotations.get(CONST_ROADMAP_IMPLEMENT_ANNOTATION_PROGRESS_AT), moment)
    digest = _digest(api, job.name)
    silence = int(moment - last)
    if digest and digest != seen:
        change = _progress(api, job, deadline, elapsed, digest, moment, limits)
        if change is not None:
            _record(change)
        return change
    if silence >= limits.deadline_stall_seconds:
        change = _stall(api, job, deadline, elapsed, silence)
        _record(change, silence)
        return change
    return None


def manage_deadlines(
    api: ClusterJobs, jobs: Iterable[ClusterJob], *, now: datetime | None = None
) -> tuple[DeadlineChange, ...]:
    """Move the deadline of each Job of `jobs` that the Service made and that has not ended and
    has a start time: extend it on progress, or end the Job when its log stayed the same for the
    stall time. Return the changes of the deadline.

    Raises ClusterJobError when the API refuses a patch.
    """
    moment = (now or datetime.now(UTC)).timestamp()
    changes: list[DeadlineChange] = []
    for job in jobs:
        if (
            job.state is JobState.RUNNING
            and is_managed(job)
            and CONST_ROADMAP_IMPLEMENT_ANNOTATION_STALLED not in job.annotations
            and job.started is not None
            and job.deadline is not None
            and (change := _watch(api, job, job.deadline, job.started, moment))
        ):
            changes.append(change)
    return tuple(changes)


__all__ = ["DeadlineChange", "is_managed", "manage_deadlines"]
