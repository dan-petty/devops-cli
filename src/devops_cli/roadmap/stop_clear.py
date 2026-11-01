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

**Cost.** A Blocked stop that no rule clears costs one request in each round: the listing of its
comments. The issue is read again only when a rule holds, right before the write.
"""

from __future__ import annotations

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
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.implement import retry_asked
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stage import StageFailure, write_each
from devops_cli.roadmap.status_sync import StatusFacts, derive_status, job_holds, plan_merged
from devops_cli.roadmap.store import (
    GitHubState,
    ImplementRecordKey,
    IssueComment,
    Item,
    ItemField,
    RoadmapStore,
)

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


class _TemplateDigest:
    """The digest of the template, read at most one time in a pass. A read that fails fails the
    same way for each caller, with no second request."""

    def __init__(self, read: Callable[[], str | None]) -> None:
        self._read = read
        self._asked = False
        self._digest: str | None = None
        self._error: ClusterJobError | None = None

    def __call__(self) -> str | None:
        if not self._asked:
            self._asked = True
            try:
                self._digest = self._read()
            except ClusterJobError as error:
                self._error = error
        if self._error is not None:
            raise self._error
        return self._digest


def _new_digest(item: Item, template_digest: Callable[[], str | None]) -> str | None:
    """The digest of the template when it differs from the digest of the stop, else None. A stop
    with no digest on record gives None without a read of the template."""
    recorded = item.job_record.get(ImplementRecordKey.JOB_DIGEST)
    if not recorded:
        return None
    current = template_digest()
    return current if current and current != recorded else None


def _rule(
    item: Item, comments: list[IssueComment], template_digest: Callable[[], str | None]
) -> tuple[ClearRule, str | None] | None:
    """The rule that clears the stop of `item`, with the new digest for the rule `digest`, or None.
    A retry wins, and needs no read of the template."""
    if retry_asked(comments):
        return ClearRule.RETRY, None
    new = _new_digest(item, template_digest)
    return (ClearRule.DIGEST, new) if new is not None else None


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
    """Clear the stop of `item` by the first rule that holds. The rule comes from the cached item
    and one listing of the comments. Only when a rule holds, the issue is read again: an item that
    a person, another lane or an earlier write changed since `item` was read is left for the next
    round. The write comes before the comment, because the comment starts with the marker of the
    job and so ends a retry that the stop waited for."""
    comments = store.comments_on(item.number)
    if _rule(item, comments, template_digest) is None:
        return
    current = store.item(item.number)
    if current is None or not is_service_stop(current):
        return
    if (decided := _rule(current, comments, template_digest)) is None:
        return
    rule, new = decided
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
    of CronJob `devops-cli-runner`; the pass reads it at most one time, a read that fails
    included, and only for a stop that records a digest. An item that fails does not stop the others; a rate limit, rejected
    credentials and the stop of the Service stop the pass."""
    template_digest = _TemplateDigest(digest)
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
