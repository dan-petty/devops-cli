"""The listing snapshot shared through the cache Valkey, over the local file of each process (#4668).

A process with no local snapshot, such as an intake pod that starts with an empty home, reads the
whole listing: one request for each 100 issues. ADR 0023 section 2 adds a shared tier in the cache
Valkey `valkey-devops`, so a cold process starts from the newest copy and reads only the changes
since its watermark. GitHub stays the source of truth (ADR 0001): each copy can be dropped and read
again in full.

`ValkeySnapshotStore` keeps the snapshot of a repository in one hash,
`valkey:roadmap:v1:snapshot:<owner>/<name>` with the casefolded name of `RepoRef.key`, with the
field `meta` (the schema key, the time of the last full read, the watermark, and a digest of the
records) and one zlib JSON `IssueRecord` for each issue number. One field for each record keeps
each value far under the bound of 1 MiB; the whole snapshot of devops-cli is about 38 MB of JSON
and 14 MB with zlib. The key lives `DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS` after its last save.

- A load reads `meta`, then the records with `HSCAN`. It uses the records only when their digest
  is the one of `meta`, so a copy that another writer changed during the scan is not used, and a
  new `meta` of the same records does not spoil the scan. Two lanes that load one repository at
  the same time share one scan: a load takes a lock for its repository, and a load that waited
  takes the records of the scan of the other load. A load keeps its records as the known records
  only when no save or load of the process replaced the known records during its scan. The budget
  of a load, `DEFAULT_BRAIN_SNAPSHOT_LOAD_BUDGET_SECONDS`, starts when it misses the known records,
  and covers the wait for the scan of another lane, the `HSCAN`, and the inflate and validation of
  the records. A value that does not parse, a time with no UTC offset, a record under a field that
  is not its issue number, and a record that expands past `DEFAULT_BRAIN_VALUE_MAX_BYTES` make the
  copy a miss: the values are untrusted. So does a sum of expanded records past
  `DEFAULT_BRAIN_SNAPSHOT_LOAD_MAX_BYTES` (128 MiB), the total bound of one load.
- A write of records whose JSON passes the total bound of one load writes nothing and counts
  `oversize`, so no writer of the store stores a copy that no load accepts.
- A write is made only when its watermark is not older than the stored one, or when the stored
  copy has another schema key (ADR 0023 section 4). The check and the write are one WATCH and
  MULTI/EXEC; a writer whose EXEC fails writes nothing and does not try again, because the other
  writer is as new or newer.
- A save of the records that the stored copy already holds, with no newer full read or
  watermark, writes no record: it sets the TTL again and counts `unchanged`. When the store knows
  the stored records (they have the digest of the snapshot, or of the copy that this process
  last wrote or read), a write sends only the changed and removed records and the new `meta`.
  Else it writes all records to a temporary key with a TTL and RENAMEs it onto the snapshot key.
  Either way an issue that left the repository leaves the shared copy. A save compresses only
  the records that it sends: a store that knows the stored records compares each record with the
  known record of its number before it encodes, so an older or unchanged save compresses no
  record.

`TieredSnapshotStore` is the `SnapshotStore` that intake and the lanes read through. It loads the
local and the shared copy, drops a copy with another schema key or a full read older than
`DEFAULT_ROADMAP_INTAKE_SNAPSHOT_MAX_AGE_HOURS`, and takes the copy with the newer watermark. It
saves the shared copy first and then the local file. While Valkey fails, it reads and writes the
local file only. The shared tier holds the data of a private repository only for the process that
sends the `sweep` ACL user of `valkey-devops` (#4704), which holds `~valkey:roadmap:*` (ADR 0023
section 8): the store reads the visibility of a repository only after Valkey answered, and uses
and writes the shared copy for a public answer, and for a private answer only under `SWEEP_USER`.
The module `visibility` holds the check and its answers, which the issue cache also uses (#7292).
A private answer under any other user or none removes the shared copy of a repository that became
private. A failed visibility read gives an unknown answer: the store does not read or write the
shared copy, and reads the visibility again after `DEFAULT_BRAIN_VISIBILITY_FAILURE_TTL_SECONDS`.
A save comes only after a public answer, which a process keeps for
`DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS` (30 min). An unknown answer removes a copy whose last save,
which the TTL of the key gives, is older than that time, and leaves a fresher copy (#6611). Valkey
reads the TTL again and removes the key in one script, so a save during the visibility read keeps
the copy. Thus a short failure keeps a fresh copy, and a failure that goes on, such as a token that
cannot see a repository that became private, removes the copy at most 1 hour after the change, at
the first run after that: the bound that the owner accepted on 2026-11-21.
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
import uuid
import zlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cached_property
from itertools import batched
from typing import Any, Final

from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError

from devops_cli.config.constants import (
    CONST_VALKEY_ROADMAP_PREFIX,
    BrainRead,
    BrainStore,
    BrainWrite,
    ValkeyCacheError,
)
from devops_cli.config.defaults import (
    DEFAULT_BRAIN_SNAPSHOT_LOAD_BUDGET_SECONDS,
    DEFAULT_BRAIN_SNAPSHOT_LOAD_MAX_BYTES,
    DEFAULT_BRAIN_SNAPSHOT_SCAN_COUNT,
    DEFAULT_BRAIN_SNAPSHOT_TEMPORARY_TTL_SECONDS,
    DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS,
    DEFAULT_BRAIN_VALUE_MAX_BYTES,
    DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS,
    DEFAULT_GH_REST_PER_PAGE,
    DEFAULT_ROADMAP_INTAKE_SNAPSHOT_MAX_AGE_HOURS,
)
from devops_cli.core import clock
from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.stores.github_store import GhRunner, GitHubRoadmapStore
from devops_cli.roadmap.stores.listing_snapshot import (
    LISTING_SCHEMA_KEY,
    ListingSnapshot,
    SnapshotStore,
)
from devops_cli.roadmap.stores.store import IssueRecord
from devops_cli.roadmap.stores.visibility import (
    Visibility,
    configured_valkey_user,
    for_user,
    reset_visibility,
    visibility_of,
)
from devops_cli.telemetry.instruments import (
    BRAIN_GITHUB_REQUESTS_SAVED_TOTAL,
    VALKEY_CACHE_ERRORS_TOTAL,
    emit,
)
from devops_cli.valkey.cache import ValkeyCacheTier, shared_cache_tier
from devops_cli.valkey.tiered import count_read, count_write

logger = logging.getLogger(__name__)

# The field of the hash that holds the facts of the snapshot.
META_FIELD: Final = "meta"
_MAX_AGE: Final = timedelta(hours=DEFAULT_ROADMAP_INTAKE_SNAPSHOT_MAX_AGE_HOURS)


class SharedMeta(BaseModel):
    """The `meta` field of a shared snapshot. `digest` is the digest of its records (see
    `_records_digest`), so two `meta` values that are equal name the same records. Each time
    names its UTC offset: a value with no offset does not parse, and the copy is a miss."""

    model_config = ConfigDict(frozen=True)

    schema_key: str
    full_at: AwareDatetime
    watermark: AwareDatetime
    digest: str


class _RecordTimes(BaseModel):
    """The times of a record of a shared snapshot. Each names its UTC offset, so the merge and
    the watermark can compare it with the times that GitHub gives."""

    model_config = ConfigDict(from_attributes=True)

    created_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None
    closed_at: AwareDatetime | None = None


@dataclass(frozen=True)
class HeldMeta:
    """The `meta` of a shared snapshot as Valkey gave it: its bytes, its facts when they parse,
    and the time that its key had left in milliseconds (`PTTL`), read in the same round trip."""

    raw: bytes
    meta: SharedMeta | None
    pttl: int


@dataclass(frozen=True)
class _Seen:
    """The records of a shared copy that a store wrote or read: the bytes of its `meta`, a digest
    and the length of the JSON of each record by number, and the records, the highest number
    first."""

    raw: bytes
    digests: Mapping[str, bytes]
    lengths: Mapping[str, int]
    issues: tuple[IssueRecord, ...]

    @cached_property
    def digest(self) -> str:
        """The digest of the records, as `meta` names it."""
        return _records_digest(self.digests)

    @cached_property
    def by_number(self) -> Mapping[int, IssueRecord]:
        """The records by issue number."""
        return {issue.number: issue for issue in self.issues}


def snapshot_key(repo: str) -> str:
    """The Valkey key of the shared snapshot of `repo`, with the casefolded name of `RepoRef`, so
    each spelling of a name gives one key."""
    return f"{CONST_VALKEY_ROADMAP_PREFIX}:snapshot:{RepoRef(repo).key}"


def _digest(text: bytes) -> bytes:
    return hashlib.blake2b(text, digest_size=16).digest()


def _records_digest(digests: Mapping[str, bytes]) -> str:
    """One digest of the records whose digests by number are `digests`."""
    total = hashlib.blake2b(digest_size=16)
    for number in sorted(digests):
        total.update(number.encode() + b"\0" + digests[number])
    return total.hexdigest()


def _listing(repo: str, meta: SharedMeta, issues: tuple[IssueRecord, ...]) -> ListingSnapshot:
    """The snapshot of `repo` with the facts of `meta` and the records `issues`."""
    return ListingSnapshot(
        repo=repo,
        schema_key=meta.schema_key,
        full_at=meta.full_at,
        watermark=meta.watermark,
        issues=issues,
    )


def _newest_first(issues: tuple[IssueRecord, ...] | list[IssueRecord]) -> tuple[IssueRecord, ...]:
    return tuple(sorted(issues, key=lambda issue: issue.number, reverse=True))


def _parsed(raw: bytes) -> SharedMeta | None:
    """The facts of a `meta` field; None when it does not parse."""
    try:
        return SharedMeta.model_validate_json(raw)
    except ValidationError as exc:
        logger.debug("The meta field of a shared snapshot does not parse: %s", exc.error_count())
        return None


def may_replace(stored: SharedMeta | None, schema_key: str, watermark: datetime) -> bool:
    """Whether a write of a snapshot with `schema_key` and `watermark` may replace the stored
    copy: there is none, it has another schema key, or its watermark is not newer."""
    return stored is None or stored.schema_key != schema_key or watermark >= stored.watermark


@dataclass(frozen=True)
class _Budget:
    """The budget of one load of the shared snapshot of `repo`, which started at the monotonic
    reading `started`: `DEFAULT_BRAIN_SNAPSHOT_LOAD_BUDGET_SECONDS`."""

    repo: str
    started: float

    def passed(self, step: str) -> bool:
        """Whether the load passed its budget. A load that passed it logs `step` and counts
        `devops_cli_valkey_cache_errors_total{op="hscan",error="budget"}`: `HSCAN` is the command
        of the load."""
        if clock.monotonic() - self.started <= DEFAULT_BRAIN_SNAPSHOT_LOAD_BUDGET_SECONDS:
            return False
        logger.info(
            "The load of the shared snapshot of %s passed its budget of %s s in %s.",
            self.repo,
            DEFAULT_BRAIN_SNAPSHOT_LOAD_BUDGET_SECONDS,
            step,
        )
        emit(
            VALKEY_CACHE_ERRORS_TOTAL,
            1,
            {"op": "hscan", "error": ValkeyCacheError.BUDGET.value},
        )
        return True


@dataclass
class ValkeySnapshotStore:
    """The snapshots of the repositories in the cache Valkey, one hash for each repository.

    The store keeps the records of the shared copy of each repository that it last wrote or
    read, so a later write encodes and sends only the changed records, and a later load of the
    same records, such as by another lane of the process, sends no `HSCAN`. It keeps one lock for
    each repository that it loads, so the loads of one repository at the same time send one
    scan. It keeps them by the casefolded
    name of `RepoRef.key`, as `snapshot_key` does, so each spelling of a name uses the one set of
    known records of its one key. One store lives for a process (`shared_snapshot_store`).
    `load_max_bytes` is the total bound of the expanded records of one load, and of the record
    JSON of one write. `compress` gives the value of a record from its JSON; a write calls it only
    for the records that it sends.
    """

    tier: ValkeyCacheTier
    load_max_bytes: int = DEFAULT_BRAIN_SNAPSHOT_LOAD_MAX_BYTES
    compress: Callable[[bytes], bytes] = zlib.compress
    _seen: dict[str, _Seen] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _loads: dict[str, threading.Lock] = field(default_factory=dict, init=False, repr=False)

    def meta(self, repo: str) -> HeldMeta | None:
        """The `meta` of the shared snapshot of `repo` and the TTL of its key, in one round trip;
        None when there is none or the read fails. `tier.is_open` after the call tells a
        failure."""
        read = self.tier.hget_with_ttl(snapshot_key(repo), META_FIELD)
        raw, pttl = (None, -2) if read is None else read
        return None if raw is None else HeldMeta(raw, _parsed(raw), pttl)

    def records(self, repo: str, held: HeldMeta) -> ListingSnapshot | None:
        """The shared snapshot whose `meta` is `held`; None when the read fails, passes its
        budget, finds a record that does not parse, or finds records that are not the ones that
        `held` names, because another writer changed them.

        A load whose records the store knows takes them and sends no command. Else it takes the
        lock of the repository before it scans, and a load that waited for the scan of another
        load takes the records of that scan, so the loads of one repository at the same time
        send one scan. The budget of a load starts when it misses the known records, and covers
        the wait for the lock, the `HSCAN`, and the inflate and validation of the records, so a
        load that waits stops after one budget, even when the scan of the other load failed."""
        meta = held.meta
        if meta is None:
            return None
        known = self._known(repo, meta)
        if known is not None:
            return _listing(repo, meta, known.issues)
        budget = _Budget(repo, clock.monotonic())
        with self._lock:
            load = self._loads.setdefault(RepoRef(repo).key, threading.Lock())
        with load:
            before = self._entry(repo)
            known = _matching(before, meta)
            if known is not None:
                return _listing(repo, meta, known.issues)
            if budget.passed("the wait for the load of another lane"):
                return None
            return self._load(repo, held, meta, budget, before)

    def _load(
        self,
        repo: str,
        held: HeldMeta,
        meta: SharedMeta,
        budget: _Budget,
        before: _Seen | None,
    ) -> ListingSnapshot | None:
        """Scan, inflate, digest and validate the records of the shared snapshot whose `meta` is
        `held`. Each step stops when the load passes `budget`. The records become the known
        records of `repo` only when the known records are still `before`, the ones that the load
        missed: a save or a load of the process during the scan keeps its newer records."""
        values = self._scan(repo, budget)
        if values is None:
            return None
        values.pop(META_FIELD, None)
        texts = _decompressed(repo, values, self.load_max_bytes, budget)
        if texts is None:
            return None
        digests = _digests(texts)
        if _records_digest(digests) != meta.digest:
            logger.info("The shared snapshot of %s changed during its load.", repo)
            return None
        issues: list[IssueRecord] = []
        for number, text in texts.items():
            try:
                issue = IssueRecord.model_validate_json(text)
                _RecordTimes.model_validate(issue)
            except ValidationError as exc:
                logger.info("A record of the shared snapshot of %s does not parse: %s", repo, exc)
                return None
            if number != str(issue.number):
                logger.info(
                    "A record of the shared snapshot of %s is not under the field of its number.",
                    repo,
                )
                return None
            issues.append(issue)
            if budget.passed("the validation of the records"):
                return None
        newest_first = _newest_first(issues)
        seen = _Seen(held.raw, digests, _lengths(texts), newest_first)
        key = RepoRef(repo).key
        with self._lock:
            if self._seen.get(key) is before:
                self._seen[key] = seen
        return _listing(repo, meta, newest_first)

    def _scan(self, repo: str, budget: _Budget) -> dict[str, bytes] | None:
        """Every field of the shared snapshot of `repo` by `HSCAN`; None when a step fails or the
        load passes `budget` before its last step. The inflate checks the budget after the last
        step."""
        key = snapshot_key(repo)
        values: dict[str, bytes] = {}
        cursor = 0
        while True:
            step = self.tier.hscan(key, cursor, DEFAULT_BRAIN_SNAPSHOT_SCAN_COUNT)
            if step is None:
                return None
            cursor, fields = step
            values |= fields
            if cursor == 0:
                return values
            if budget.passed("the HSCAN"):
                return None

    def load(self, repo: str) -> ListingSnapshot | None:
        held = self.meta(repo)
        return None if held is None else self.records(repo, held)

    def save(self, snapshot: ListingSnapshot) -> None:
        """Write `snapshot` when it may replace the shared copy, and count the result."""
        count_write(BrainStore.SNAPSHOT, self.write(snapshot, self.meta(snapshot.repo)))

    def write(self, snapshot: ListingSnapshot, held: HeldMeta | None) -> BrainWrite:
        """Write `snapshot` over the shared copy whose `meta` was `held`, and return the result.

        Each check comes before a record is compressed. An older snapshot gives `older` before a
        record is encoded. Records whose JSON passes `load_max_bytes` in total give `oversize`
        and write nothing, because no load would accept them. A store that knows the stored
        records encodes only the records that are not equal to them, and takes the digest and
        the length of each equal record from them. Records that the stored copy holds, with no
        newer full read or watermark, give `unchanged`."""
        stored = None if held is None else held.meta
        if stored is not None and not may_replace(stored, snapshot.schema_key, snapshot.watermark):
            return BrainWrite.OLDER
        known = self._known(snapshot.repo, stored)
        texts, digests, lengths = _encoded(snapshot.issues, known)
        if sum(lengths.values()) > self.load_max_bytes:
            logger.info(
                "The records of %s pass the bound of %s bytes of one shared load, so the shared "
                "tier gets no copy.",
                snapshot.repo,
                self.load_max_bytes,
            )
            return BrainWrite.OVERSIZE
        if any(len(text) > DEFAULT_BRAIN_VALUE_MAX_BYTES for text in texts.values()):
            return BrainWrite.OVERSIZE
        meta = SharedMeta(
            schema_key=snapshot.schema_key,
            full_at=snapshot.full_at,
            watermark=snapshot.watermark,
            digest=_records_digest(digests),
        )
        issues = _newest_first(snapshot.issues)
        if held is None or stored is None:
            return self._replace(snapshot, texts)
        if _holds(stored, meta):
            self.tier.expire(snapshot_key(snapshot.repo), DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS)
            seen = _Seen(held.raw, digests, lengths, issues)
            return self._kept(snapshot.repo, seen, BrainWrite.UNCHANGED)
        before = known.digests if known is not None else None
        if before is None and stored.digest == meta.digest:
            before = digests
        if before is not None:
            records = self._compressed(
                {
                    number: text
                    for number, text in texts.items()
                    if before.get(number) != digests[number]
                }
            )
            if records is None:
                return BrainWrite.OVERSIZE
            seen = _Seen(meta.model_dump_json().encode(), digests, lengths, issues)
            if self._update(snapshot.repo, held.raw, before, seen, records):
                return self._kept(snapshot.repo, seen)
        return self._replace(snapshot, texts if known is None else _encoded(snapshot.issues)[0])

    def _entry(self, repo: str) -> _Seen | None:
        """The records of the shared copy of `repo` that this process last wrote or read."""
        with self._lock:
            return self._seen.get(RepoRef(repo).key)

    def _known(self, repo: str, stored: SharedMeta | None) -> _Seen | None:
        """The records of the stored copy whose `meta` is `stored`, when this process last wrote
        or read them."""
        return _matching(self._entry(repo), stored)

    def _compressed(self, texts: Mapping[str, bytes]) -> dict[str, bytes] | None:
        """The value of each record JSON of `texts`; None when a value passes
        `DEFAULT_BRAIN_VALUE_MAX_BYTES`."""
        records = {number: self.compress(text) for number, text in texts.items()}
        if any(len(value) > DEFAULT_BRAIN_VALUE_MAX_BYTES for value in records.values()):
            return None
        return records

    def _update(
        self,
        repo: str,
        raw: bytes,
        before: Mapping[str, bytes],
        seen: _Seen,
        records: Mapping[str, bytes],
    ) -> bool:
        """Send the records `records`, remove the records of `before` that `seen` does not hold,
        and write the `meta` of `seen`, in one transaction, when the stored `meta` is still
        `raw`."""
        key = snapshot_key(repo)
        changed = [word for number, value in records.items() for word in (number, value)]
        removed = [number for number in before if number not in seen.digests]

        def decide(current: bytes | None) -> list[tuple[Any, ...]]:
            if current != raw:
                return []
            return [
                *([("HSET", key, *changed)] if changed else []),
                *([("HDEL", key, *removed)] if removed else []),
                ("HSET", key, META_FIELD, seen.raw),
                ("EXPIRE", key, DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS),
            ]

        return bool(self.tier.watch_and_write(key, META_FIELD, decide))

    def _replace(self, snapshot: ListingSnapshot, texts: Mapping[str, bytes]) -> BrainWrite:
        """Write every record of `snapshot`, whose JSON by number is `texts`, to a temporary key,
        then RENAME it onto the snapshot key when the stored copy may still be replaced. The
        `meta` names the digest of `texts`."""
        records = self._compressed(texts)
        if records is None:
            return BrainWrite.OVERSIZE
        digests = _digests(texts)
        meta = SharedMeta(
            schema_key=snapshot.schema_key,
            full_at=snapshot.full_at,
            watermark=snapshot.watermark,
            digest=_records_digest(digests),
        )
        seen = _Seen(
            meta.model_dump_json().encode(),
            digests,
            _lengths(texts),
            _newest_first(snapshot.issues),
        )
        key = snapshot_key(snapshot.repo)
        temporary = f"{key}:next:{uuid.uuid4().hex}"
        written = self.tier.hset(temporary, {META_FIELD: seen.raw}) is not None and (
            self.tier.expire(temporary, DEFAULT_BRAIN_SNAPSHOT_TEMPORARY_TTL_SECONDS)
        )
        for batch in batched(records.items(), DEFAULT_BRAIN_SNAPSHOT_SCAN_COUNT, strict=False):
            written = written and self.tier.hset(temporary, dict(batch)) is not None

        def decide(current: bytes | None) -> list[tuple[Any, ...]]:
            if current is not None and not may_replace(
                _parsed(current), meta.schema_key, meta.watermark
            ):
                return []
            return [
                ("RENAME", temporary, key),
                ("EXPIRE", key, DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS),
            ]

        renamed = self.tier.watch_and_write(key, META_FIELD, decide) if written else None
        if renamed:
            return self._kept(snapshot.repo, seen)
        self.tier.unlink(temporary)
        return BrainWrite.SKIPPED if renamed is None else BrainWrite.OLDER

    def _kept(self, repo: str, seen: _Seen, result: BrainWrite = BrainWrite.SHARED) -> BrainWrite:
        with self._lock:
            self._seen[RepoRef(repo).key] = seen
        return result

    def remove(self, repo: str) -> bool:
        """Remove the shared snapshot of `repo`; whether Valkey removed a key."""
        with self._lock:
            self._seen.pop(RepoRef(repo).key, None)
        return bool(self.tier.unlink(snapshot_key(repo)))

    def remove_stale(self, repo: str) -> bool:
        """Remove the shared snapshot of `repo` when its last save is older than
        `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS`; whether Valkey removed a key. Valkey reads the TTL
        of the key and removes the key in one script, so a save that came after the read of
        `meta` keeps the key."""
        removed = bool(self.tier.unlink_if_expiring(snapshot_key(repo), _STALE_TTL_BELOW_MS))
        if removed:
            with self._lock:
                self._seen.pop(RepoRef(repo).key, None)
        return removed


def _matching(seen: _Seen | None, stored: SharedMeta | None) -> _Seen | None:
    """`seen` when it holds the records that `stored` names."""
    if seen is None or stored is None or seen.digest != stored.digest:
        return None
    return seen


def _holds(stored: SharedMeta, mine: SharedMeta) -> bool:
    """Whether the stored copy already holds what `mine` would write: the same schema key and
    records, and a full read and a watermark that are not older."""
    return (
        stored.schema_key == mine.schema_key
        and stored.digest == mine.digest
        and stored.watermark >= mine.watermark
        and stored.full_at >= mine.full_at
    )


def _digests(texts: Mapping[str, bytes]) -> dict[str, bytes]:
    return {number: _digest(text) for number, text in texts.items()}


def _lengths(texts: Mapping[str, bytes]) -> dict[str, int]:
    return {number: len(text) for number, text in texts.items()}


def _encoded(
    issues: Iterable[IssueRecord], known: _Seen | None = None
) -> tuple[dict[str, bytes], dict[str, bytes], dict[str, int]]:
    """The JSON of each record of `issues` that `known` does not hold, and the digest and the
    length of the JSON of each record, by number. A record that is equal to the known record of
    its number keeps the digest and the length of that record and is not encoded: the records are
    frozen, and equal records give equal JSON."""
    texts: dict[str, bytes] = {}
    digests: dict[str, bytes] = {}
    lengths: dict[str, int] = {}
    for issue in issues:
        number = str(issue.number)
        if known is not None and known.by_number.get(issue.number) == issue:
            digests[number] = known.digests[number]
            lengths[number] = known.lengths[number]
            continue
        text = issue.model_dump_json().encode()
        texts[number] = text
        digests[number] = _digest(text)
        lengths[number] = len(text)
    return texts, digests, lengths


def _decompressed(
    repo: str, values: Mapping[str, bytes], max_bytes: int, budget: _Budget
) -> dict[str, bytes] | None:
    """The JSON of each record; None when a value is not whole zlib data or expands past
    `DEFAULT_BRAIN_VALUE_MAX_BYTES`, which no writer of the store writes, when the sum of the
    expanded records passes `max_bytes`, or when the load passes `budget`. The sum and the budget
    are checked after each record, so a load expands at most the total bound and one record."""
    texts: dict[str, bytes] = {}
    total = 0
    for number, value in values.items():
        expander = zlib.decompressobj()
        try:
            text = expander.decompress(value, DEFAULT_BRAIN_VALUE_MAX_BYTES)
        except zlib.error as exc:
            logger.info("A record of the shared snapshot of %s is not zlib data: %s", repo, exc)
            return None
        if expander.unconsumed_tail or not expander.eof:
            logger.info(
                "A record of the shared snapshot of %s is cut off or expands past %s bytes.",
                repo,
                DEFAULT_BRAIN_VALUE_MAX_BYTES,
            )
            return None
        total += len(text)
        if total > max_bytes:
            logger.info(
                "The records of the shared snapshot of %s expand past the bound of %s bytes.",
                repo,
                max_bytes,
            )
            return None
        texts[number] = text
        if budget.passed("the inflate of the records"):
            return None
    return texts


_STORE_LOCK = threading.Lock()
_stores: list[ValkeySnapshotStore] = []


def shared_snapshot_store() -> ValkeySnapshotStore | None:
    """The one shared snapshot store of the process, over `shared_cache_tier()`; None when the
    process has no Valkey tier."""
    tier = shared_cache_tier()
    if tier is None:
        return None
    with _STORE_LOCK:
        if not _stores or _stores[0].tier is not tier:
            _stores[:] = [ValkeySnapshotStore(tier)]
        return _stores[0]


def repository_visibility(repo: str, *, runner: GhRunner | None = None) -> Visibility:
    """The visibility of `repo` that GitHub gives, through the one check of the shared tier
    (`visibility_of`): read once for each repository and the time to live of its answer. A failed
    read gives `Visibility.UNKNOWN`: the shared tier gets no data that could be private (ADR 0023
    section 8), keeps only a copy saved in the last `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS` and
    removes an older one."""
    store = GitHubRoadmapStore(repo) if runner is None else GitHubRoadmapStore(repo, runner=runner)
    return visibility_of(repo, store.repository_is_private)


def reset_shared_snapshots() -> None:
    """Drop the shared snapshot store and the visibility answers of the process, as a new
    process starts."""
    with _STORE_LOCK:
        _stores.clear()
    reset_visibility()


def _now() -> datetime:
    return datetime.now(UTC)


# A shared copy whose key has less time left than this is stale: its last save is older than
# `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS`.
_STALE_TTL_BELOW_MS = int(
    (DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS - DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS) * 1000
)


def _stale(held: HeldMeta) -> bool:
    """Whether the last save of the shared copy whose `meta` is `held` is older than
    `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS`: each save sets the TTL of the key to
    `DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS`, so the age is that TTL less the time that the key has
    left. A save comes only after a public answer, which a process keeps for that time, so the copy
    of a repository that became private is stale at most two times that time after the change. A
    key with no TTL (-1) and a key that went (-2) give no age and are not stale."""
    return 0 <= held.pttl < _STALE_TTL_BELOW_MS


@dataclass(frozen=True)
class TieredSnapshotStore:
    """The local snapshot store of a process and the shared one in Valkey, as one store.

    `shared` gives the shared store of the process, None when there is no Valkey tier.
    `visibility` gives the visibility of a repository. `clock` gives the time now, which the age
    of a full read is measured from. `user` gives the ACL user that the process sends, which
    `valkey.username` names: only `SWEEP_USER` shares a private repository.
    """

    local: SnapshotStore
    shared: Callable[[], ValkeySnapshotStore | None] = shared_snapshot_store
    visibility: Callable[[str], Visibility] = repository_visibility
    clock: Callable[[], datetime] = _now
    schema_key: str = LISTING_SCHEMA_KEY
    user: Callable[[], str | None] = configured_valkey_user

    def load(self, repo: str) -> ListingSnapshot | None:
        local = self.local.load(repo)
        shared = self.shared()
        held = None if shared is None else shared.meta(repo)
        if shared is None or (held is None and shared.tier.is_open):
            count_read(BrainStore.SNAPSHOT, BrainRead.FALLBACK)
            return local
        visibility = self._checked(shared, repo, held)
        if visibility is not Visibility.PUBLIC:
            private = visibility is Visibility.PRIVATE
            count_read(BrainStore.SNAPSHOT, BrainRead.PRIVATE if private else BrainRead.UNKNOWN)
            return local
        now = self.clock()
        local_fit = self._fit(local, now)
        meta = None if held is None else held.meta
        if (
            held is None
            or meta is None
            or not self._fit(meta, now)
            or (local is not None and local_fit and local.watermark >= meta.watermark)
        ):
            count_read(BrainStore.SNAPSHOT, BrainRead.LOCAL if local_fit else BrainRead.SOURCE)
            return local
        copy = shared.records(repo, held)
        if copy is None:
            count_read(BrainStore.SNAPSHOT, BrainRead.FALLBACK)
            return local
        count_read(BrainStore.SNAPSHOT, BrainRead.SHARED)
        if not local_fit:
            pages = math.ceil(len(copy.issues) / DEFAULT_GH_REST_PER_PAGE)
            emit(BRAIN_GITHUB_REQUESTS_SAVED_TOTAL, pages, {"store": BrainStore.SNAPSHOT.value})
        return copy

    def save(self, snapshot: ListingSnapshot) -> None:
        """Write the shared copy, then the local file."""
        count_write(BrainStore.SNAPSHOT, self._share(snapshot))
        self.local.save(snapshot)

    def _share(self, snapshot: ListingSnapshot) -> BrainWrite:
        shared = self.shared()
        held = None if shared is None else shared.meta(snapshot.repo)
        if shared is None or (held is None and shared.tier.is_open):
            return BrainWrite.SKIPPED
        visibility = self._checked(shared, snapshot.repo, held)
        if visibility is Visibility.PRIVATE:
            return BrainWrite.PRIVATE
        if visibility is Visibility.UNKNOWN:
            return BrainWrite.UNKNOWN
        return shared.write(snapshot, held)

    def _checked(self, shared: ValkeySnapshotStore, repo: str, held: HeldMeta | None) -> Visibility:
        """The visibility of `repo`, where a private repository is public to `SWEEP_USER`: the
        process that sends that ACL user reads and writes the shared copy of a private repository
        (#4704). A private answer of any other user or of none removes the shared copy, so the
        shared tier keeps no copy that its role cannot read. An unknown answer removes a copy
        whose last save is older than `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS` (`_stale`), and
        leaves a fresher copy as it is. Valkey checks the age again when it removes the copy, so a
        save during the visibility read keeps it."""
        visibility = for_user(self.visibility(repo), self.user())
        if held is None:
            return visibility
        if visibility is Visibility.PRIVATE:
            removed, reason = shared.remove(repo), "is private now"
        elif visibility is Visibility.UNKNOWN and _stale(held):
            removed = shared.remove_stale(repo)
            reason = (
                f"has no save in the last {DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS:.0f} s, and whose "
                "visibility is not known"
            )
        else:
            return visibility
        if removed:
            logger.info("The shared tier held the listing of %s, which %s.", repo, reason)
            count_write(BrainStore.SNAPSHOT, BrainWrite.REMOVED)
        return visibility

    def _fit(self, held: ListingSnapshot | SharedMeta | None, now: datetime) -> bool:
        """Whether a run can read the changes from `held`: it has this schema key, and its last
        full read is younger than the max age."""
        return (
            held is not None
            and held.schema_key == self.schema_key
            and now - held.full_at < _MAX_AGE
        )


__all__ = [
    "META_FIELD",
    "HeldMeta",
    "SharedMeta",
    "TieredSnapshotStore",
    "ValkeySnapshotStore",
    "may_replace",
    "repository_visibility",
    "reset_shared_snapshots",
    "shared_snapshot_store",
    "snapshot_key",
]
