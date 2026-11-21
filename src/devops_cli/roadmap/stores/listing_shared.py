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
each value far under the bound of 1 MiB; the whole snapshot of devops-cli is about 14 MB. The key
lives `DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS` after its last save.

- A load reads `meta`, then the records with `HSCAN`, and stops when it passes
  `DEFAULT_BRAIN_SNAPSHOT_LOAD_BUDGET_SECONDS`. It uses the records only when their digest is the
  one of `meta`, so a copy that another writer changed during the scan is not used, and a new
  `meta` of the same records does not spoil the scan. A value that does not parse, a time with
  no UTC offset and a record that expands past `DEFAULT_BRAIN_VALUE_MAX_BYTES` make the copy a
  miss: the values are untrusted.
- A write is made only when its watermark is not older than the stored one, or when the stored
  copy has another schema key (ADR 0023 section 4). The check and the write are one WATCH and
  MULTI/EXEC; a writer whose EXEC fails writes nothing and does not try again, because the other
  writer is as new or newer.
- A save of the records that the stored copy already holds, with no newer full read or
  watermark, writes no record: it sets the TTL again and counts `unchanged`. When the store knows
  the stored records (they have the digest of the snapshot, or of the copy that this process
  last wrote or read), a write sends only the changed and removed records and the new `meta`.
  Else it writes all records to a temporary key with a TTL and RENAMEs it onto the snapshot key.
  Either way an issue that left the repository leaves the shared copy.

`TieredSnapshotStore` is the `SnapshotStore` that intake and the lanes read through. It loads the
local and the shared copy, drops a copy with another schema key or a full read older than
`DEFAULT_ROADMAP_INTAKE_SNAPSHOT_MAX_AGE_HOURS`, and takes the copy with the newer watermark. It
saves the shared copy first and then the local file. While Valkey fails, it reads and writes the
local file only. Until `valkey-devops` has role ACL users (#4704), the shared tier holds no data
of a private repository (ADR 0023 section 8): the store reads the visibility of a repository only
after Valkey answered, a failed visibility read counts as private, and the store removes the
shared copy of a repository that became private.
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
import uuid
import zlib
from collections.abc import Callable, Mapping
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
    DEFAULT_BRAIN_SNAPSHOT_SCAN_COUNT,
    DEFAULT_BRAIN_SNAPSHOT_TEMPORARY_TTL_SECONDS,
    DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS,
    DEFAULT_BRAIN_VALUE_MAX_BYTES,
    DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS,
    DEFAULT_GH_REST_PER_PAGE,
    DEFAULT_ROADMAP_INTAKE_SNAPSHOT_MAX_AGE_HOURS,
)
from devops_cli.core import clock
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.stores.github_store import GhRunner, GitHubRoadmapStore
from devops_cli.roadmap.stores.listing_snapshot import (
    LISTING_SCHEMA_KEY,
    ListingSnapshot,
    SnapshotStore,
)
from devops_cli.roadmap.stores.store import IssueRecord
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
    """The `meta` of a shared snapshot as Valkey gave it: its bytes, and its facts when they parse."""

    raw: bytes
    meta: SharedMeta | None


@dataclass(frozen=True)
class _Seen:
    """The records of a shared copy that a store knows: the bytes of its `meta`, a digest of the
    JSON of each record by number, and the records, the highest number first, when the store
    wrote or read them."""

    raw: bytes
    digests: Mapping[str, bytes]
    issues: tuple[IssueRecord, ...] | None = None

    @cached_property
    def digest(self) -> str:
        """The digest of the records, as `meta` names it."""
        return _records_digest(self.digests)


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


def may_replace(stored: SharedMeta | None, mine: SharedMeta) -> bool:
    """Whether a write of `mine` may replace the stored copy: there is none, it has another schema
    key, or its watermark is not newer than that of `mine`."""
    return (
        stored is None or stored.schema_key != mine.schema_key or mine.watermark >= stored.watermark
    )


def _count_budget() -> None:
    emit(
        VALKEY_CACHE_ERRORS_TOTAL,
        1,
        {"op": "hscan", "error": ValkeyCacheError.BUDGET.value},
    )


@dataclass
class ValkeySnapshotStore:
    """The snapshots of the repositories in the cache Valkey, one hash for each repository.

    The store keeps the records of the shared copy of each repository that it last wrote or
    read, so a later write sends only the changed records, and a later load of the same records,
    such as by another lane of the process, sends no `HSCAN`. One store lives for a process
    (`shared_snapshot_store`).
    """

    tier: ValkeyCacheTier
    _seen: dict[str, _Seen] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def meta(self, repo: str) -> HeldMeta | None:
        """The `meta` of the shared snapshot of `repo`; None when there is none or the read
        fails. `tier.is_open` after the call tells a failure."""
        raw = self.tier.hget(snapshot_key(repo), META_FIELD)
        return None if raw is None else HeldMeta(raw, _parsed(raw))

    def records(self, repo: str, held: HeldMeta) -> ListingSnapshot | None:
        """The shared snapshot whose `meta` is `held`; None when the read fails, passes its
        budget, finds a record that does not parse, or finds records that are not the ones that
        `held` names, because another writer changed them."""
        if held.meta is None:
            return None
        with self._lock:
            before = self._seen.get(repo)
        if before is not None and before.issues is not None and before.digest == held.meta.digest:
            return _listing(repo, held.meta, before.issues)
        values = self._scan(repo)
        if values is None:
            return None
        values.pop(META_FIELD, None)
        texts = _decompressed(repo, values)
        if texts is None:
            return None
        digests = _digests(texts)
        if _records_digest(digests) != held.meta.digest:
            logger.info("The shared snapshot of %s changed during its load.", repo)
            return None
        try:
            issues = [IssueRecord.model_validate_json(text) for text in texts.values()]
            for issue in issues:
                _RecordTimes.model_validate(issue)
        except ValidationError as exc:
            logger.info("A record of the shared snapshot of %s does not parse: %s", repo, exc)
            return None
        newest_first = _newest_first(issues)
        with self._lock:
            self._seen[repo] = _Seen(held.raw, digests, newest_first)
        return _listing(repo, held.meta, newest_first)

    def _scan(self, repo: str) -> dict[str, bytes] | None:
        """Every field of the shared snapshot of `repo` by `HSCAN`; None when a step fails or the
        scan passes its budget."""
        key = snapshot_key(repo)
        started = clock.monotonic()
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
            if clock.monotonic() - started > DEFAULT_BRAIN_SNAPSHOT_LOAD_BUDGET_SECONDS:
                logger.info(
                    "The load of the shared snapshot of %s passed its budget of %s s.",
                    repo,
                    DEFAULT_BRAIN_SNAPSHOT_LOAD_BUDGET_SECONDS,
                )
                _count_budget()
                return None

    def load(self, repo: str) -> ListingSnapshot | None:
        held = self.meta(repo)
        return None if held is None else self.records(repo, held)

    def save(self, snapshot: ListingSnapshot) -> None:
        """Write `snapshot` when it may replace the shared copy, and count the result."""
        count_write(BrainStore.SNAPSHOT, self.write(snapshot, self.meta(snapshot.repo)))

    def write(self, snapshot: ListingSnapshot, held: HeldMeta | None) -> BrainWrite:
        """Write `snapshot` over the shared copy whose `meta` was `held`, and return the result."""
        texts = {str(issue.number): issue.model_dump_json().encode() for issue in snapshot.issues}
        records = {number: zlib.compress(text) for number, text in texts.items()}
        if any(
            len(value) > DEFAULT_BRAIN_VALUE_MAX_BYTES
            for value in (*texts.values(), *records.values())
        ):
            return BrainWrite.OVERSIZE
        digests = _digests(texts)
        meta = SharedMeta(
            schema_key=snapshot.schema_key,
            full_at=snapshot.full_at,
            watermark=snapshot.watermark,
            digest=_records_digest(digests),
        )
        stored = None if held is None else held.meta
        if held is not None and not may_replace(stored, meta):
            return BrainWrite.OLDER
        issues = _newest_first(snapshot.issues)
        if held is not None and stored is not None and _holds(stored, meta):
            self.tier.expire(snapshot_key(snapshot.repo), DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS)
            return self._kept(snapshot.repo, _Seen(held.raw, digests, issues), BrainWrite.UNCHANGED)
        seen = _Seen(meta.model_dump_json().encode(), digests, issues)
        known = self._known(snapshot.repo, held, seen)
        if known is not None and self._update(snapshot.repo, known, seen, records):
            return self._kept(snapshot.repo, seen)
        return self._replace(snapshot.repo, meta, seen, records)

    def _known(self, repo: str, held: HeldMeta | None, mine: _Seen) -> _Seen | None:
        """The records of the stored copy whose `meta` is `held`, when the store knows them: they
        are the records of `mine`, or the records that this process last wrote or read."""
        stored = None if held is None else held.meta
        if held is None or stored is None:
            return None
        with self._lock:
            before = self._seen.get(repo)
        for known in (mine, before):
            if known is not None and stored.digest == known.digest:
                return _Seen(held.raw, known.digests)
        return None

    def _update(self, repo: str, before: _Seen, seen: _Seen, records: dict[str, bytes]) -> bool:
        """Send the changed and removed records and the new `meta` in one transaction, when the
        stored `meta` is still the one of `before`."""
        key = snapshot_key(repo)
        changed = [
            word
            for number, value in records.items()
            if before.digests.get(number) != seen.digests[number]
            for word in (number, value)
        ]
        removed = [number for number in before.digests if number not in records]

        def decide(current: bytes | None) -> list[tuple[Any, ...]]:
            if current != before.raw:
                return []
            return [
                *([("HSET", key, *changed)] if changed else []),
                *([("HDEL", key, *removed)] if removed else []),
                ("HSET", key, META_FIELD, seen.raw),
                ("EXPIRE", key, DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS),
            ]

        return bool(self.tier.watch_and_write(key, META_FIELD, decide))

    def _replace(
        self, repo: str, meta: SharedMeta, seen: _Seen, records: dict[str, bytes]
    ) -> BrainWrite:
        """Write every record to a temporary key, then RENAME it onto the snapshot key when the
        stored copy may still be replaced."""
        key = snapshot_key(repo)
        temporary = f"{key}:next:{uuid.uuid4().hex}"
        written = self.tier.hset(temporary, {META_FIELD: seen.raw}) is not None and (
            self.tier.expire(temporary, DEFAULT_BRAIN_SNAPSHOT_TEMPORARY_TTL_SECONDS)
        )
        for batch in batched(records.items(), DEFAULT_BRAIN_SNAPSHOT_SCAN_COUNT, strict=False):
            written = written and self.tier.hset(temporary, dict(batch)) is not None

        def decide(current: bytes | None) -> list[tuple[Any, ...]]:
            if current is not None and not may_replace(_parsed(current), meta):
                return []
            return [
                ("RENAME", temporary, key),
                ("EXPIRE", key, DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS),
            ]

        renamed = self.tier.watch_and_write(key, META_FIELD, decide) if written else None
        if renamed:
            return self._kept(repo, seen)
        self.tier.unlink(temporary)
        return BrainWrite.SKIPPED if renamed is None else BrainWrite.OLDER

    def _kept(self, repo: str, seen: _Seen, result: BrainWrite = BrainWrite.SHARED) -> BrainWrite:
        with self._lock:
            self._seen[repo] = seen
        return result

    def remove(self, repo: str) -> bool:
        """Remove the shared snapshot of `repo`; whether Valkey removed a key."""
        with self._lock:
            self._seen.pop(repo, None)
        return bool(self.tier.unlink(snapshot_key(repo)))


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


def _decompressed(repo: str, values: Mapping[str, bytes]) -> dict[str, bytes] | None:
    """The JSON of each record; None when a value is not whole zlib data or expands past
    `DEFAULT_BRAIN_VALUE_MAX_BYTES`, which no writer of the store writes."""
    texts: dict[str, bytes] = {}
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
        texts[number] = text
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


_VISIBILITY_LOCK = threading.Lock()
# The visibility of each repository that this process read, by `RepoRef.key`: whether it is
# public, and when.
_visibility: dict[str, tuple[bool, float]] = {}


def repository_is_public(repo: str, *, runner: GhRunner | None = None) -> bool:
    """Whether GitHub says that `repo` is public, read once for each repository and
    `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS`. A failed read counts as private and is not kept, so
    the shared tier gets no data that could be private (ADR 0023 section 8)."""
    now = clock.monotonic()
    name = RepoRef(repo).key
    with _VISIBILITY_LOCK:
        held = _visibility.get(name)
    if held is not None and now - held[1] < DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS:
        return held[0]
    store = GitHubRoadmapStore(repo) if runner is None else GitHubRoadmapStore(repo, runner=runner)
    try:
        public = not store.repository_is_private()
    except DevOpsCLIError as exc:
        logger.warning(
            "The visibility of %s is not known, so the shared tier does not hold its listing: %s",
            repo,
            exc,
        )
        return False
    with _VISIBILITY_LOCK:
        _visibility[name] = (public, now)
    return public


def reset_shared_snapshots() -> None:
    """Drop the shared snapshot store and the visibility answers of the process, as a new
    process starts."""
    with _STORE_LOCK:
        _stores.clear()
    with _VISIBILITY_LOCK:
        _visibility.clear()


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class TieredSnapshotStore:
    """The local snapshot store of a process and the shared one in Valkey, as one store.

    `shared` gives the shared store of the process, None when there is no Valkey tier.
    `is_public` says whether a repository is public. `clock` gives the time now, which the age of
    a full read is measured from.
    """

    local: SnapshotStore
    shared: Callable[[], ValkeySnapshotStore | None] = shared_snapshot_store
    is_public: Callable[[str], bool] = repository_is_public
    clock: Callable[[], datetime] = _now
    schema_key: str = LISTING_SCHEMA_KEY

    def load(self, repo: str) -> ListingSnapshot | None:
        local = self.local.load(repo)
        shared = self.shared()
        held = None if shared is None else shared.meta(repo)
        if shared is None or (held is None and shared.tier.is_open):
            count_read(BrainStore.SNAPSHOT, BrainRead.FALLBACK)
            return local
        if not self._public(shared, repo, held):
            count_read(BrainStore.SNAPSHOT, BrainRead.PRIVATE)
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
        if not self._public(shared, snapshot.repo, held):
            return BrainWrite.PRIVATE
        return shared.write(snapshot, held)

    def _public(self, shared: ValkeySnapshotStore, repo: str, held: HeldMeta | None) -> bool:
        """Whether `repo` is public. The shared copy of a repository that is not public is
        removed, so the shared tier keeps no copy of a repository that became private."""
        if self.is_public(repo):
            return True
        if held is not None and shared.remove(repo):
            logger.info("The shared tier held the listing of %s, which is not public now.", repo)
            count_write(BrainStore.SNAPSHOT, BrainWrite.REMOVED)
        return False

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
    "repository_is_public",
    "reset_shared_snapshots",
    "shared_snapshot_store",
    "snapshot_key",
]
