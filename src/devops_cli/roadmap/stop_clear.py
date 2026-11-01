"""The clear rules of a stop (#2912): how an item leaves Blocked.

A stop of the implement job sets the Status Blocked and records `implement.stopped`
(`implement_run.py`, `implement_submit.py`). The Service never runs the item again on its own.
Two rules take it out of Blocked, and the row `implement` runs them before it plans:

- **`retry`**: the owner, a member or a collaborator commented `implement: retry` after the last
  comment of the job. It clears at once, whatever the runner image.
- **`digest`**: the digest in the template of CronJob `devops-cli-runner` differs from
  `implement.job_digest`, the digest of the Job that left the stop. A new runner image may fix the
  cause, so the Service tries the item once more.

A clear removes `implement.stopped`, sets the Status that `derive_status` gives (Ready, or Planned
when the plan is on the default branch), and comments the rule that ran.

**Never a loop.** The next Job overwrites `implement.job_digest` with the digest of the template.
A stop on that digest finds both digests equal, so the rule `digest` does not fire again until a
release rolls another image. Each digest clears a stop at most one time. A stop with no digest on
record, or a template with no digest, is cleared only by a retry.

**What it clears.** Only a stop that the Service set: the item is open, holds Blocked with the
label that a job last recorded, and records a stop. A Blocked label that a person set stays. The
Service takes no item that an agent or a person claimed, or that a runner Job still holds. The
pass reads the issue again before it writes, and skips an item that changed since the cached read.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_STATUS_BLOCKED,
)
from devops_cli.exceptions import GitHubRateLimitError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.implement import retry_asked
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stage import StageFailure, write_each
from devops_cli.roadmap.status_sync import StatusFacts, derive_status, job_holds, plan_merged
from devops_cli.roadmap.store import GitHubState, ImplementRecordKey, Item, ItemField, RoadmapStore

logger = logging.getLogger(__name__)


class ClearRule(StrEnum):
    """The rule that cleared a stop. The comment of the Service names it."""

    RETRY = "retry"
    DIGEST = "digest"


@dataclass(frozen=True)
class StopsCleared:
    """What a pass did: the numbers of the items whose stop it cleared, and the items it could not
    write."""

    cleared: tuple[int, ...] = ()
    failed: tuple[StageFailure, ...] = ()


def is_service_stop(item: Item) -> bool:
    """Whether `item` holds a stop that the Service set and may clear: it is open and Blocked with
    the label that a job last recorded, a stop is on record, no runner Job holds it, and no agent
    or person claimed it."""
    return (
        item.state is GitHubState.OPEN
        and item.status == CONST_ROADMAP_STATUS_BLOCKED
        and item.job_record.get(ItemField.STATUS) == CONST_ROADMAP_STATUS_BLOCKED
        and bool(item.job_record.get(ImplementRecordKey.STOPPED))
        and not job_holds(item)
        and claimed_by(item) is None
    )


def _new_digest(item: Item, template_digest: Callable[[], str | None]) -> str | None:
    """The digest of the template when it differs from the digest of the stop, else None. A stop
    with no digest on record gives None without a read of the template."""
    recorded = item.job_record.get(ImplementRecordKey.JOB_DIGEST)
    if not recorded:
        return None
    current = template_digest()
    return current if current and current != recorded else None


def _comment(rule: ClearRule, item: Item, status: str, current: str | None) -> str:
    texts = MESSAGES.roadmap
    stopped = item.job_record.get(ImplementRecordKey.STOPPED)
    if rule is ClearRule.RETRY:
        return texts.stop_clear_retry.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
            rule=rule.value,
            stopped=stopped,
            status=status,
        )
    return texts.stop_clear_digest.format(
        marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
        rule=rule.value,
        stopped=stopped,
        old=item.job_record.get(ImplementRecordKey.JOB_DIGEST),
        new=current,
        status=status,
    )


def _clear_one(
    store: RoadmapStore,
    item: Item,
    planned: PlannedChanges,
    template_digest: Callable[[], str | None],
    cleared: list[int],
) -> None:
    """Clear the stop of `item` by the first rule that holds. The issue is read again first: an
    item that a person, another lane or an earlier write changed since `item` was read is left for
    the next round. The write comes before the comment, because the comment starts with the marker
    of the job and so ends a retry that the stop waited for."""
    current = store.item(item.number)
    if current is None or not is_service_stop(current):
        return
    if retry_asked(store.comments_on(current.number)):
        rule, new = ClearRule.RETRY, None
    elif (new := _new_digest(current, template_digest)) is not None:
        rule = ClearRule.DIGEST
    else:
        return
    status = derive_status(StatusFacts(plan_merged=plan_merged(current, planned)))
    store.set_field(current, ItemField.STATUS, status, marks={ImplementRecordKey.STOPPED: None})
    store.comment(current.number, _comment(rule, current, status, new))
    cleared.append(current.number)


def clear_stops(
    store: RoadmapStore,
    *,
    planned: PlannedChanges,
    digest: Callable[[], str | None],
) -> StopsCleared:
    """Clear each stop of the Service that a rule clears. `digest` reads the digest in the template
    of CronJob `devops-cli-runner`; the pass reads it at most one time, and only for a stop that
    records a digest. An item that fails does not stop the others; a rate limit, rejected
    credentials and the stop of the Service stop the pass."""
    template_digest = functools.cache(digest)
    cleared: list[int] = []
    failed: list[StageFailure] = []
    writes = [
        (item, partial(_clear_one, store, item, planned, template_digest, cleared))
        for item in store.items()
        if is_service_stop(item)
    ]
    write_each(writes, [], failed, also_stop=(GitHubRateLimitError,))
    logger.info("The stop pass cleared %d item(s) and failed for %d", len(cleared), len(failed))
    return StopsCleared(tuple(cleared), tuple(failed))


__all__ = ["ClearRule", "StopsCleared", "clear_stops", "is_service_stop"]
