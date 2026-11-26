"""`brain-sync`: the step of an alternatives round that copies the checks of the listing snapshot
into the brain index (#4676, ADR 0023 section 3).

The alternatives row of the Service reads the listing of a repository, checks its items and
writes each result to GitHub. `sync_alternatives_round` then copies the results into the index of
`valkey-roadmap` as the ACL user `brain`. The step reads only the issues that the store of the
round holds, which are the listing snapshot with the writes of the round, so it sends no GitHub
request. A round whose check is off, as for a private repository, reads no listing and makes no
sync, so the index holds no entry of a private repository.

**The watermark.** The sync keeps the `updated_at` and the number of the last issue that it
examined. It copies each issue that changed after that place, oldest change first, at most
`CONST_ROADMAP_BRAIN_SYNC_MAX_ISSUES` in one round, and the next round goes on from the place. So
a round after an outage copies each issue that changed in it, and a sync of an empty index
copies each check. A changed issue with no check moves the place and writes nothing.

**The entries of the other items.** Each copy of an item also writes the items that name its tool
and its reference repositories, and its near items: the other items of the same repository that
name the same tool, the newest check first, at most `CONST_ROADMAP_BRAIN_ITEM_MAX_NEAR`. They come
from the checks of the whole snapshot. An entry never names an item of another repository.

**Fail soft.** With no `roadmap.state.url`, or while the store does not answer, the sync ends
with no error and adds one `fallback` to `devops_cli_brain_reads_total` for the store
`brain_index`. It then writes no sync time, so the lag of the next sync shows the gap. A reader
of the index has a miss, and the next round copies what this one did not.

**Instruments.** A sync that completes sends `devops_cli_brain_entries` and
`devops_cli_brain_sync_lag_seconds`, the time since the end of the last sync, and adds the first
reads of the round to `devops_cli_brain_first_reads_total`: the checks of the round whose item the
index held no entry for. Each copy adds one write of the store `brain_index` to
`devops_cli_brain_writes_total`.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, NamedTuple

from devops_cli.config.constants import (
    CONST_ROADMAP_BRAIN_ITEM_MAX_NEAR,
    CONST_ROADMAP_BRAIN_SYNC_MAX_ISSUES,
    BrainRead,
    BrainStore,
    BrainWrite,
)
from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.brain_entries import BrainEntry, entry_of
from devops_cli.roadmap.brain_index import BrainIndex, Related, Watermark, Written
from devops_cli.roadmap.job_result import RoadmapJob
from devops_cli.roadmap.stores.store import as_utc
from devops_cli.telemetry.instruments import (
    BRAIN_ENTRIES,
    BRAIN_FIRST_READS_TOTAL,
    BRAIN_SYNC_LAG,
    emit,
)
from devops_cli.valkey.cache import roadmap_state_tier
from devops_cli.valkey.tiered import count_read, count_write

if TYPE_CHECKING:
    from devops_cli.roadmap.alternatives import AlternativesPlan
    from devops_cli.roadmap.stores.store import IssueRecord, RoadmapStore
    from devops_cli.valkey.cache import ValkeyCacheTier

logger = logging.getLogger(__name__)

_STORE: Final[BrainStore] = BrainStore.BRAIN_INDEX
# The place of an issue with no `updated_at`: before each watermark, so only a sync of an empty
# index copies it.
_NEVER: Final[datetime] = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class BrainSync:
    """What one sync did: the items that it wrote, the items whose entry of a newer check it
    kept, the first reads of the round, the item entries of the repository after it, and the
    seconds since the end of the last sync. `fallback` says that the store is not configured or
    did not answer, and then the sync sent no instrument."""

    copied: int = 0
    kept: int = 0
    first_reads: int = 0
    entries: int | None = None
    lag_seconds: float | None = None
    fallback: bool = False


class _Place(NamedTuple):
    """Where an issue is in the order of the sync: its `updated_at`, then its number."""

    changed: datetime
    number: int


def _place(issue: IssueRecord) -> _Place:
    changed = _NEVER if issue.updated_at is None else as_utc(issue.updated_at)
    return _Place(changed, issue.number)


def _changed_since(issues: Iterable[IssueRecord], held: Watermark) -> list[IssueRecord]:
    """The issues of `issues` after the place of `held`, the oldest change first; each issue
    when `held` has no place. A pull request is no issue of the index."""
    after = None if held.changed is None else _Place(as_utc(held.changed), held.number)
    found = [
        issue
        for issue in issues
        if not issue.pull_request and (after is None or _place(issue) > after)
    ]
    return sorted(found, key=_place)


class _Checks:
    """The checks of one snapshot: the entry of each issue that holds a check, and the items
    that name each tool and each reference repository."""

    def __init__(self, issues: Iterable[IssueRecord]) -> None:
        found = (entry_of(issue) for issue in issues)
        self.entries: dict[int, BrainEntry] = {entry.number: entry for entry in found if entry}
        self._by_tool: defaultdict[str, list[BrainEntry]] = defaultdict(list)
        self._by_reference: defaultdict[str, list[int]] = defaultdict(list)
        for entry in self.entries.values():
            if entry.tool_id:
                self._by_tool[entry.tool_id].append(entry)
            for url in entry.refs:
                self._by_reference[url].append(entry.number)

    def related(self, entry: BrainEntry) -> Related:
        """What the other checks of the snapshot say of `entry`."""
        members = self._by_tool.get(entry.tool_id, [])
        newest_first = sorted(
            members, key=lambda member: (-member.checked_at.timestamp(), member.number)
        )
        near = [member.number for member in newest_first if member.number != entry.number]
        return Related(
            near=tuple(near[:CONST_ROADMAP_BRAIN_ITEM_MAX_NEAR]),
            tool_items=tuple(sorted(member.number for member in members)),
            reference_items={url: tuple(sorted(self._by_reference[url])) for url in entry.refs},
        )


@dataclass
class _Run:
    """The count of one sync while it copies, and the place of the last issue that it examined."""

    copied: int = 0
    kept: int = 0
    first_reads: int = 0
    place: _Place | None = None
    failed: bool = False


def _copy_one(
    index: BrainIndex, entry: BrainEntry, related: Related, run: _Run, first: bool
) -> None:
    """Write `entry` and count the result in `run`. `first` says that a check of this round wrote
    the entry, so a write of a new entry is a first read."""
    written = index.write(entry, related)
    if written is None:
        run.failed = True
        count_write(_STORE, BrainWrite.SKIPPED)
    elif written is Written.KEPT:
        run.kept += 1
        count_write(_STORE, BrainWrite.OLDER)
    else:
        run.copied += 1
        run.first_reads += int(first and written is Written.NEW)
        count_write(_STORE, BrainWrite.SHARED)


def _copy_changed(
    index: BrainIndex,
    checks: _Checks,
    changed: Sequence[IssueRecord],
    *,
    limit: int,
    checked: Collection[int],
) -> _Run:
    """Copy the entry of each issue of `changed` in order, at most `limit` of them, and stop at
    the first write that the store does not answer."""
    run = _Run()
    for issue in changed:
        if run.copied + run.kept >= limit:
            break
        entry = checks.entries.get(issue.number)
        if entry is not None:
            _copy_one(index, entry, checks.related(entry), run, issue.number in checked)
        if run.failed:
            break
        run.place = _place(issue)
    return run


def _fallback(repo: RepoRef, run: _Run | None = None) -> BrainSync:
    """The result of a sync that did not complete: one `fallback`, and what it copied before."""
    count_read(_STORE, BrainRead.FALLBACK)
    done = run or _Run()
    logger.info(
        "The brain index of %s has no store, or its store did not answer: %d items copied.",
        repo.key,
        done.copied,
    )
    return BrainSync(copied=done.copied, kept=done.kept, fallback=True)


def _observe(repo: RepoRef, result: BrainSync) -> None:
    """Send the instruments of a sync that completed."""
    attributes = {"store": _STORE.value, "repo": repo.key}
    if result.entries is not None:
        emit(BRAIN_ENTRIES, result.entries, attributes)
    if result.lag_seconds is not None:
        emit(BRAIN_SYNC_LAG, result.lag_seconds, attributes)
    emit(BRAIN_FIRST_READS_TOTAL, result.first_reads, {"row": RoadmapJob.ALTERNATIVES.value})


def sync_brain_index(
    repo: str,
    issues: Sequence[IssueRecord],
    *,
    tier: ValkeyCacheTier | None,
    checked: Collection[int] = (),
    limit: int = CONST_ROADMAP_BRAIN_SYNC_MAX_ISSUES,
    now: datetime | None = None,
) -> BrainSync:
    """Copy the checks of `issues`, the issues of the listing snapshot of `repo`, that changed
    since the watermark into the brain index through `tier`, at most `limit` of them. `checked`
    names the items that the round checked: a new entry of one of them is a first read. With no
    tier, or while the store does not answer, the sync ends with `fallback`."""
    moment = now or datetime.now(UTC)
    ref = RepoRef(repo)
    if tier is None:
        return _fallback(ref)
    index = BrainIndex(tier, ref)
    held = index.watermark()
    if held is None:
        return _fallback(ref)
    run = _copy_changed(
        index, _Checks(issues), _changed_since(issues, held), limit=limit, checked=checked
    )
    place = Watermark() if run.place is None else Watermark(run.place.changed, run.place.number)
    if run.failed:
        # The place of the last copy, with no sync time: the next sync goes on from it.
        index.advance(place)
        return _fallback(ref, run)
    if not index.advance(Watermark(place.changed, place.number, synced_at=moment)):
        return _fallback(ref, run)
    keys = index.item_keys()
    result = BrainSync(
        copied=run.copied,
        kept=run.kept,
        first_reads=run.first_reads,
        entries=None if keys is None else len(keys),
        lag_seconds=None if held.synced_at is None else (moment - held.synced_at).total_seconds(),
    )
    _observe(ref, result)
    logger.info(
        "The brain index of %s: %d items copied, %d kept, %s entries.",
        ref.key,
        result.copied,
        result.kept,
        result.entries,
    )
    return result


def sync_alternatives_round(
    store: RoadmapStore, plan: AlternativesPlan, *, now: datetime | None = None
) -> BrainSync | None:
    """The `brain-sync` step of the alternatives round that gave `plan`: copy the checks of the
    issues that `store` holds into the brain index of the repository. `store` read its listing
    for the selection of the round and keeps each write of the round, so the step sends no GitHub
    request. None for a round whose check is off or that is a dry run: such a round read no
    listing, and a private repository gets no entry."""
    if plan.off_reason is not None or plan.dry_run:
        return None
    return sync_brain_index(
        plan.repo,
        store.issues(),
        tier=roadmap_state_tier(),
        checked=frozenset(check.item.number for check in plan.checks),
        now=now,
    )


__all__ = ["BrainSync", "sync_alternatives_round", "sync_brain_index"]
