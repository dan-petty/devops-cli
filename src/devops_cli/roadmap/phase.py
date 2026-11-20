"""Pipeline phase derivation, phase age, and stall detection for roadmap items (#5495).

An item progresses through pipeline phases. The pure function `phase(item)` derives the current
phase from labels, the job record, and pull request facts. An item is stalled when its phase age
exceeds `roadmap.stall.hours`, no cluster unit runs for it, and it has no claim and no recorded
person cause.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Final

from devops_cli.config.constants import (
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_IN_REVIEW,
    CONST_ROADMAP_STATUS_PLANNED,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.github.client import PullStatus
from devops_cli.github.repo_ref import RepoRef
from devops_cli.k8s.cluster_job import ITEM_LABEL, REPO_LABEL
from devops_cli.k8s.cluster_job_api import ClusterJobs, JobState
from devops_cli.roadmap.stores.store import (
    AlternativesRecordKey,
    GitHubState,
    ImplementRecordKey,
    Item,
    OwnerQuestionRecordKey,
    RefineRecordKey,
    StageRecordKey,
)

logger = logging.getLogger(__name__)


class Phase(StrEnum):
    """The pipeline phases of a roadmap item (#5495).

    A phase whose job is not built yet stays out until its item ships.
    """

    NEW = "new"
    JUDGED = "judged"
    RESEARCHED = "researched"
    READY = "ready"
    PLAN_CHECKED = "plan-checked"
    STAGED = "staged"
    PLANNED = "planned"
    TESTS_PUSHED = "tests-pushed"
    CODE_CHECKED = "code-checked"
    IN_REVIEW = "in-review"
    READY_FOR_REVIEW = "ready-for-review"
    REVIEWED = "reviewed"
    MERGED = "merged"


ACTIVE_PHASES: Final[tuple[Phase, ...]] = (
    Phase.NEW,
    Phase.JUDGED,
    Phase.READY,
    Phase.STAGED,
    Phase.PLANNED,
    Phase.IN_REVIEW,
    Phase.READY_FOR_REVIEW,
    Phase.MERGED,
)


def _delivery_phase(
    item: Item, pulls: Mapping[int, PullStatus] | None, record: Mapping[Any, Any]
) -> Phase | None:
    pr_raw = record.get(ImplementRecordKey.PR)
    pr_num = int(pr_raw) if pr_raw and str(pr_raw).isdigit() else None
    delivery_pr = pulls.get(pr_num) if (pulls and pr_num) else None
    if delivery_pr is not None:
        if delivery_pr.merged:
            return Phase.MERGED
        if delivery_pr.state == "open" and not delivery_pr.draft:
            return Phase.READY_FOR_REVIEW
        if delivery_pr.state == "open":
            return Phase.IN_REVIEW
    if item.status == CONST_ROADMAP_STATUS_IN_REVIEW or "status/in-review" in item.labels:
        return Phase.READY_FOR_REVIEW
    if (
        item.status == CONST_ROADMAP_STATUS_IN_PROGRESS
        or "status/in-progress" in item.labels
        or pr_raw is not None
        or bool(record.get(ImplementRecordKey.JOB))
        or bool(record.get(ImplementRecordKey.BRANCH))
    ):
        return Phase.IN_REVIEW
    return None


def _stage_phase(
    item: Item, pulls: Mapping[int, PullStatus] | None, record: Mapping[Any, Any]
) -> Phase | None:
    pr_raw = record.get(StageRecordKey.PR)
    pr_num = int(pr_raw) if pr_raw and str(pr_raw).isdigit() else None
    stage_pr = pulls.get(pr_num) if (pulls and pr_num) else None
    if stage_pr is not None and (
        stage_pr.merged or (stage_pr.state == "open" and not stage_pr.draft)
    ):
        return Phase.PLANNED
    if (
        item.status == CONST_ROADMAP_STATUS_PLANNED
        or "status/planned" in item.labels
        or bool(record.get(StageRecordKey.READY))
    ):
        return Phase.PLANNED
    if pr_raw is not None or bool(record.get(StageRecordKey.BRANCH)):
        return Phase.STAGED
    return None


def _is_judged(record: Mapping[Any, Any]) -> bool:
    return (
        record.get(RefineRecordKey.JUDGE) == "approved"
        or record.get(AlternativesRecordKey.VERDICT) is not None
        or record.get(AlternativesRecordKey.CHECKED_AT) is not None
        or record.get(RefineRecordKey.SECTION_HASH) is not None
        or record.get(RefineRecordKey.COMMENTED_AT) is not None
    )


def phase(item: Item, pulls: Mapping[int, PullStatus] | None = None) -> Phase:
    """Derive the pipeline phase of an item from its labels, job record, and PR facts (#5495)."""
    if item.state is GitHubState.CLOSED:
        return Phase.MERGED

    record = item.job_record
    if (deliv := _delivery_phase(item, pulls, record)) is not None:
        return deliv
    if (staged := _stage_phase(item, pulls, record)) is not None:
        return staged
    if (
        item.status == CONST_ROADMAP_STATUS_READY
        or "status/ready" in item.labels
        or record.get(RefineRecordKey.NEXT_STEP) == "ready"
    ):
        return Phase.READY
    if _is_judged(record):
        return Phase.JUDGED
    return Phase.NEW


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


_PHASE_STATUS_LABELS: Final[dict[Phase, str]] = {
    Phase.READY: "status/ready",
    Phase.PLANNED: "status/planned",
    Phase.IN_REVIEW: "status/in-progress",
    Phase.READY_FOR_REVIEW: "status/in-review",
    Phase.NEW: "status/new",
}


def _phase_label_time(
    item_times: Mapping[str, datetime] | None, item_phase: Phase
) -> datetime | None:
    if not item_times:
        return None
    label = _PHASE_STATUS_LABELS.get(item_phase)
    return item_times.get(label) if label else None


def _phase_record_times(record: Mapping[Any, Any], item_phase: Phase) -> list[datetime]:
    keys: tuple[Any, ...] = ()
    if item_phase == Phase.JUDGED:
        keys = (AlternativesRecordKey.CHECKED_AT, RefineRecordKey.COMMENTED_AT)
    elif item_phase in (Phase.STAGED, Phase.PLANNED):
        keys = (StageRecordKey.JOB_AT,)
    elif item_phase in (Phase.IN_REVIEW, Phase.READY_FOR_REVIEW):
        keys = (ImplementRecordKey.SHA,)
    return [dt for k in keys if (dt := _parse_timestamp(record.get(k))) is not None]


def _phase_pr_time(
    record: Mapping[Any, Any],
    pulls: Mapping[int, PullStatus] | None,
    item_phase: Phase,
) -> datetime | None:
    if not pulls:
        return None
    pr_key = (
        ImplementRecordKey.PR
        if item_phase in (Phase.IN_REVIEW, Phase.READY_FOR_REVIEW)
        else StageRecordKey.PR
    )
    pr_raw = record.get(pr_key)
    if not (pr_raw and str(pr_raw).isdigit()):
        return None
    pull = pulls.get(int(pr_raw))
    if pull is None or pull.closed_at is None:
        return None
    closed = pull.closed_at
    return closed if closed.tzinfo else closed.replace(tzinfo=UTC)


def phase_age(
    item: Item,
    *,
    times: Mapping[int, Mapping[str, datetime]] | None = None,
    pulls: Mapping[int, PullStatus] | None = None,
    now: datetime | None = None,
) -> float:
    """Calculate the age of an item in its current phase in seconds (#5495).

    The phase age is the elapsed time since the newest label event, record timestamp, or PR event
    that set the phase.
    """
    moment = now or datetime.now(UTC)
    item_phase = phase(item, pulls=pulls)
    record = item.job_record
    item_times = times.get(item.number) if times else None

    candidates: list[datetime] = []
    if (label_dt := _phase_label_time(item_times, item_phase)) is not None:
        candidates.append(label_dt)
    candidates.extend(_phase_record_times(record, item_phase))
    if (pr_dt := _phase_pr_time(record, pulls, item_phase)) is not None:
        candidates.append(pr_dt)
    if item.updated_at is not None:
        dt = item.updated_at
        candidates.append(dt if dt.tzinfo else dt.replace(tzinfo=UTC))

    if not candidates:
        return 0.0
    return max(0.0, (moment - max(candidates)).total_seconds())


def has_person_cause(item: Item) -> bool:
    """Whether the item is stopped or waiting on a person by a recorded cause (#5495)."""
    record = item.job_record
    next_step = record.get(RefineRecordKey.NEXT_STEP)
    if next_step in ("person", "split", "failed"):
        return True
    returned = record.get(RefineRecordKey.RETURNED_BODY_HASH)
    if returned and returned == record.get(RefineRecordKey.BODY_HASH):
        return True
    if bool(record.get(RefineRecordKey.ALTERNATIVES_ASKED)):
        return True
    if bool(record.get(RefineRecordKey.BLOCKED_BY)):
        return True
    if bool(record.get(OwnerQuestionRecordKey.HASH)) and not bool(
        record.get(OwnerQuestionRecordKey.ANSWER)
    ):
        return True
    if bool(record.get(ImplementRecordKey.STOPPED)):
        return True
    if bool(record.get(StageRecordKey.NEEDS_SPLIT)):
        return True
    if bool(record.get(StageRecordKey.NEEDS_FIX)):
        return True
    if "verdict/fix-plan" in item.labels:
        return True
    return False


def is_stalled(
    item: Item,
    *,
    running_units: Collection[int] | None = None,
    stall_hours: int = 24,
    times: Mapping[int, Mapping[str, datetime]] | None = None,
    pulls: Mapping[int, PullStatus] | None = None,
    now: datetime | None = None,
) -> bool:
    """Whether an item is stalled (#5495).

    An item is stalled when all of these are true:
    - Its phase age is over the setting roadmap.stall.hours * 3600 (default 24h).
    - No unit of the item runs.
    - It has no person cause, and no owner/agent or owner/human claim.
    """
    if item.state is GitHubState.CLOSED:
        return False
    moment = now or datetime.now(UTC)
    age = phase_age(item, times=times, pulls=pulls, now=moment)
    if age <= stall_hours * 3600:
        return False
    if running_units is not None and item.number in running_units:
        return False
    if item.owner is not None:
        return False
    if has_person_cause(item):
        return False
    return True


def find_running_units(repo: str, jobs: ClusterJobs | None = None) -> set[int]:
    """Find the item numbers of running cluster units for a repository (#4558, #5495)."""
    try:
        api = jobs or ClusterJobs()
        repo_ref = RepoRef(repo)
        listed = api.list_jobs({REPO_LABEL: repo_ref.repo_label})
        running: set[int] = set()
        for job in listed:
            if job.state == JobState.RUNNING:
                item_str = job.labels.get(ITEM_LABEL)
                if item_str and item_str.isdigit():
                    running.add(int(item_str))
        return running
    except ClusterJobError, DevOpsCLIError, OSError:
        return set()


__all__ = [
    "ACTIVE_PHASES",
    "Phase",
    "find_running_units",
    "has_person_cause",
    "is_stalled",
    "phase",
    "phase_age",
]
