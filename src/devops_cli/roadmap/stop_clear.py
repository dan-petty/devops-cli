"""The clear rules of a stop (#2912): how an item leaves Blocked.

A stop of the implement job sets the Status Blocked and records `implement.stopped`
(`implement_run.py`, `implement_submit.py`). Three rules take it out of Blocked, and the row
`implement` runs them before it plans:

- **`retry`**: the owner, a member or a collaborator commented `implement: retry` after the last
  comment of the job. It clears at once, whatever the runner image.
- **`continue`**: the stop is `job`, which the round records for a Job that ended without a result
  (a pod that the kernel killed or evicted, a Job that the Service ended by its stall, a Job that
  no longer exists), and the class of the stop has the action `retry` in `ACTION_BY_CLASS`
  (#3721). The new Job takes the branch from `origin`, so it keeps the `wip:` commits that the run
  pushed for a group with more than one task (`implement_run.py`, #3054). A group of one task that
  passed and that no push kept runs again. The record `implement.continuations` counts the Jobs
  that the Service started this way, and the setting `roadmap.implement.continuations_per_item`
  bounds it. Only a sign in the log gives the class `oom`, because the Service reads no pod
  status (#3727). A stop of a step that the runner wrote has its own classes and rules, and is no
  continuation.
- **`digest`**: the digest in the template of CronJob `devops-cli-runner` differs from
  `implement.job_digest`, the digest of the Job that left the stop, and the class of the stop has the
  action `retry` in `ACTION_BY_CLASS` (#3481). A new runner image may fix the cause of such a stop,
  so the Service tries the item once more. A new image cannot fix a plan, a premise, a refused tool,
  a failed test or a lost test, so a stop of another class, or with no class on record, waits for a
  retry.

A clear removes `implement.stopped`, sets the Status that `derive_status` gives (Ready, or Planned
when the plan is on the default branch), and comments the rule that ran. A continuation counts
against its own limit and spends no clear by digest, and a continuation runs before the rule
`digest`, which reads the template only when no continuation applies.

**Limits of the rule `digest`.** Each clear by digest adds the class, the new digest and the time
to `implement.digest_clears` (`digest_clears.py`), and the list stays after the clear. The settings
`roadmap.implement.digest_clears_per_class` and `roadmap.implement.digest_clears_per_item` bound
the entries of one class and of one item. A stop at a limit stays Blocked until a retry. A record
that does not parse stops the rule, with a warning in the log. The comment of a clear by digest
shows at most one time in 24 hours for an item (`implement.digest_clear_commented_at`); the clear
is recorded either way. The next Job overwrites `implement.job_digest` with the digest of the
template, so a stop on that digest finds both digests equal. A stop with no digest on record, or a
template with no digest, is cleared only by a retry. The rule reads the class and the record only:
the Service holds image digests and no map from a digest to commits, so it reads no image content.
`priority_order` (`stage.py`) takes an item with no digest clear before a retried item of the same
priority, so a retried item does not keep new items from running.

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
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from functools import partial
from typing import NamedTuple

from pydantic import NonNegativeInt, TypeAdapter, ValidationError

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_IMPLEMENT_JOB_STEP,
    CONST_ROADMAP_STOP_CLEAR_COMMENT_WINDOW_HOURS,
)
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import GitHubRateLimitError
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.digest_clears import (
    DigestClear,
    encode_clears,
    last_clear_comment,
    recorded_clears,
)
from devops_cli.roadmap.failure import ACTION_BY_CLASS, FailureAction, FailureClass
from devops_cli.roadmap.implement.implement import retry_asked
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stage.stage import StageFailure, write_each
from devops_cli.roadmap.status_sync import StatusFacts, derive_status, job_holds, plan_merged
from devops_cli.roadmap.stores.store import (
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
    CONTINUE = "continue"
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
        and item.holds_service_stop()
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


class ClearLimits(NamedTuple):
    """The most clears by digest for one class of stop, and for one item, and the most continuations
    of one item. 0 turns the rule off."""

    per_class: int
    per_item: int
    continuations: int

    @classmethod
    def from_settings(cls) -> ClearLimits:
        implement = load_settings().roadmap.implement
        return cls(
            implement.digest_clears_per_class,
            implement.digest_clears_per_item,
            implement.continuations_per_item,
        )


@dataclass(frozen=True)
class _Decision:
    """The rule that clears a stop. For the rule `digest` it holds the new digest, the list of the
    clears after this one, and whether the clear writes its comment. For the rule `continue` it
    holds the count of continuations after this one."""

    rule: ClearRule
    new: str | None = None
    clears: tuple[DigestClear, ...] = ()
    failure_class: FailureClass | None = None
    comment: bool = True
    continuations: int = 0


def _retry_class(item: Item) -> FailureClass | None:
    """The class of the stop of `item` when its action in `ACTION_BY_CLASS` is `retry`, else None.
    A stop with no class on record, or with a class that the table does not hold, gives None."""
    try:
        klass = FailureClass(item.job_record.get(ImplementRecordKey.FAILURE) or "")
    except ValueError:
        return None
    return klass if ACTION_BY_CLASS.get(klass) is FailureAction.RETRY else None


_COUNT = TypeAdapter(NonNegativeInt)


def _continue_decision(item: Item, limits: ClearLimits) -> _Decision | None:
    """The rule `continue` for `item`, or None. It holds for the stop `job` of a class whose action
    is `retry`, while the Jobs that the Service started for the item are fewer than the limit. A
    record that is no count gives None, with a warning: a person clears the stop with
    `implement: retry`."""
    if item.job_record.get(ImplementRecordKey.STOPPED) != CONST_ROADMAP_IMPLEMENT_JOB_STEP:
        return None
    klass = _retry_class(item)
    if klass is None:
        return None
    try:
        used = _COUNT.validate_python(item.job_record.get(ImplementRecordKey.CONTINUATIONS) or 0)
    except ValidationError as error:
        logger.warning("Item #%d: no continuation, a record is not valid: %s", item.number, error)
        return None
    if used >= limits.continuations:
        return None
    return _Decision(ClearRule.CONTINUE, failure_class=klass, continuations=used + 1)


def _digest_decision(
    item: Item,
    template_digest: Callable[[], str | None],
    limits: ClearLimits,
    now: datetime,
) -> _Decision | None:
    """The rule `digest` for `item`, or None. The class and the limits come first, so the template
    is read only for a stop that the rule may clear. A record that does not parse gives None."""
    klass = _retry_class(item)
    if klass is None:
        return None
    try:
        clears = recorded_clears(item)
        commented = last_clear_comment(item)
    except ValidationError as error:
        logger.warning(
            "Item #%d: no clear by digest, a record is not valid: %s", item.number, error
        )
        return None
    if len(clears) >= limits.per_item:
        return None
    if sum(clear.failure_class is klass for clear in clears) >= limits.per_class:
        return None
    new = _new_digest(item, template_digest)
    if new is None:
        return None
    window = timedelta(hours=CONST_ROADMAP_STOP_CLEAR_COMMENT_WINDOW_HOURS)
    return _Decision(
        ClearRule.DIGEST,
        new,
        (*clears, DigestClear(failure_class=klass, digest=new, time=now)),
        klass,
        comment=commented is None or now - commented >= window,
    )


def _rule(
    item: Item,
    comments: list[IssueComment],
    template_digest: Callable[[], str | None],
    limits: ClearLimits,
    now: datetime,
) -> _Decision | None:
    """The rule that clears the stop of `item`, or None. A retry wins, clears a stop of any class,
    and needs no read of the template. A continuation comes before the digest, and needs no read
    either."""
    if retry_asked(comments):
        return _Decision(ClearRule.RETRY)
    return _continue_decision(item, limits) or _digest_decision(item, template_digest, limits, now)


def _comment(decision: _Decision, item: Item, status: str, limits: ClearLimits) -> str:
    texts = MESSAGES.roadmap
    stopped = item.job_record.get(ImplementRecordKey.STOPPED)
    if decision.rule is ClearRule.RETRY:
        return texts.stop_clear_retry.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
            rule=decision.rule.value,
            stopped=stopped,
            status=status,
        )
    if decision.rule is ClearRule.CONTINUE:
        return texts.stop_clear_continue.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
            rule=decision.rule.value,
            job=item.job_record.get(ImplementRecordKey.JOB),
            failure_class=decision.failure_class.value if decision.failure_class else "",
            used=decision.continuations,
            limit=limits.continuations,
            left=(
                texts.stop_clear_continue_last
                if decision.continuations >= limits.continuations
                else ""
            ),
            status=status,
        )
    return texts.stop_clear_digest.format(
        marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
        rule=decision.rule.value,
        stopped=stopped,
        old=item.job_record.get(ImplementRecordKey.JOB_DIGEST),
        new=decision.new,
        failure_class=decision.failure_class.value if decision.failure_class else "",
        per_class=limits.per_class,
        per_item=limits.per_item,
        status=status,
    )


def _marks(decision: _Decision, now: datetime) -> dict[ImplementRecordKey, str | None]:
    """What a clear writes in the record with the Status: it removes the stop, its class, the failed check and the conflicted files. A clear
    by digest also keeps the list of the clears, and the time of its comment when it writes one."""
    marks: dict[ImplementRecordKey, str | None] = {
        ImplementRecordKey.STOPPED: None,
        ImplementRecordKey.FAILURE: None,
        ImplementRecordKey.CHECK: None,
        ImplementRecordKey.CHECK_LOG: None,
        ImplementRecordKey.CONFLICT: None,
    }
    if decision.rule is ClearRule.CONTINUE:
        marks[ImplementRecordKey.CONTINUATIONS] = str(decision.continuations)
    if decision.rule is ClearRule.DIGEST:
        marks[ImplementRecordKey.DIGEST_CLEARS] = encode_clears(decision.clears)
        if decision.comment:
            marks[ImplementRecordKey.DIGEST_CLEAR_COMMENTED_AT] = now.isoformat()
    return marks


def _clear_one(
    store: RoadmapStore,
    item: Item,
    planned: PlannedChanges,
    template_digest: Callable[[], str | None],
    cleared: list[int],
    limits: ClearLimits,
    now: datetime,
) -> None:
    """Clear the stop of `item` by the first rule that holds. The rule comes from the cached item
    and one listing of the comments. Only when a rule holds, the issue is read again: an item that
    a person, another lane or an earlier write changed since `item` was read is left for the next
    round. The write comes before the comment, because the comment starts with the marker of the
    job and so ends a retry that the stop waited for."""
    comments = store.comments_on(item.number)
    if _rule(item, comments, template_digest, limits, now) is None:
        return
    current = store.item(item.number)
    if current is None or not is_service_stop(current):
        return
    if (decided := _rule(current, comments, template_digest, limits, now)) is None:
        return
    status = derive_status(StatusFacts(plan_merged=plan_merged(current, planned)))
    store.set_field(current, ItemField.STATUS, status, marks=_marks(decided, now))
    if decided.comment:
        store.comment(current.number, _comment(decided, current, status, limits))
    cleared.append(current.number)


def clear_stops(
    store: RoadmapStore,
    *,
    planned: PlannedChanges,
    digest: Callable[[], str | None],
    limits: ClearLimits | None = None,
    now: datetime | None = None,
) -> StopsCleared:
    """Clear each stop of the Service that a rule clears. `digest` reads the digest in the template
    of CronJob `devops-cli-runner`; the pass reads it at most one time, a read that fails
    included, and only for a stop that records a digest and a class that a retry can fix. `limits`
    default to the settings `roadmap.implement.digest_clears_per_class`, `_per_item` and
    `continuations_per_item`, and `now` to the current time. An item that fails does not stop the
    others; a rate limit, rejected credentials and the stop of the Service stop the pass."""
    template_digest = _TemplateDigest(digest)
    held = limits or ClearLimits.from_settings()
    moment = now or datetime.now(UTC)
    cleared: list[int] = []
    failed: list[StageFailure] = []
    writes = [
        (
            item,
            partial(_clear_one, store, item, planned, template_digest, cleared, held, moment),
        )
        for item in store.items()
        if is_service_stop(item)
    ]
    write_each(writes, [], failed, also_stop=(GitHubRateLimitError,))
    logger.info("The stop pass cleared %d item(s) and failed for %d", len(cleared), len(failed))
    return StopsCleared(tuple(cleared), tuple(failed))


__all__ = ["ClearLimits", "ClearRule", "StopsCleared", "clear_stops", "is_service_stop"]
