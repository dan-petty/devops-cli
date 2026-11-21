"""The listing snapshot shared through the cache Valkey, over the local file of each process (#4668).

Each test reads the listing through `IncrementalListing` and a `GitHubRoadmapStore` on the GitHub
API fake, with a `TieredSnapshotStore` over a local directory and the in-memory Valkey of
`shared_valkey`. A new process is a new `TieredSnapshotStore` after `reset_shared_snapshots`,
which drops the state of the shared store and the visibility answers of the process. The counters
are read on the OTLP fake.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fakeredis import FakeServer, FakeValkey

from devops_cli.github.session import get_github_session
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.listing_snapshot import (
    LISTING_SCHEMA_KEY,
    FileSnapshotStore,
    IncrementalListing,
    ListingSnapshot,
)
from devops_cli.roadmap.stores.store import IssueRecord
from devops_cli.valkey.cache import ValkeyCacheTier
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.valkey import valkey_client_on
from tests.support.roadmap_github_store import REPO, RecordedGh, issue_payload

if TYPE_CHECKING:
    from devops_cli.roadmap.stores.listing_shared import TieredSnapshotStore, ValkeySnapshotStore

STARTED = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
REPOSITORY_URL = f"https://api.github.com/repos/{REPO}"
FULL = f"/repos/{REPO}/issues?state=all&per_page=100"
SNAPSHOT_KEY = f"valkey:roadmap:v1:snapshot:{REPO}"


def _since(at: str) -> str:
    """The path of the read of the issues changed since `at`, newest change first."""
    return f"/repos/{REPO}/issues?state=all&sort=updated&direction=desc&since={at}&per_page=100"


def _issue(number: int, *, updated: str = "2026-01-01T09:00:00Z", **changes: Any) -> Any:
    """Issue `number` as the listing gives it, last changed at `updated`."""
    return issue_payload(
        number, updated_at=updated, repository_url=REPOSITORY_URL, body="Text", **changes
    )


def _public(repo: str) -> bool:
    return True


def _tiered(
    root: Path,
    *,
    at: datetime = STARTED,
    is_public: Callable[[str], bool] = _public,
    shared: Callable[[], ValkeySnapshotStore | None] | None = None,
) -> TieredSnapshotStore:
    """The tiered store of a process at `at`, over the local directory `root`.

    The import is local, so the module loads on a base without the store.
    """
    from devops_cli.roadmap.stores.listing_shared import TieredSnapshotStore, shared_snapshot_store

    return TieredSnapshotStore(
        FileSnapshotStore(root),
        shared=shared or shared_snapshot_store,
        is_public=is_public,
        clock=lambda: at,
    )


def _round(
    tiered: TieredSnapshotStore, *, at: datetime = STARTED, full: bool = False
) -> list[IssueRecord]:
    """One listing round at `at` through `tiered`: every issue, the newest first."""
    listing = IncrementalListing(tiered, full=full, clock=lambda: at)
    store = GitHubRoadmapStore(
        REPO, runner=RecordedGh({}), session=get_github_session(), listing=listing
    )
    return list(store.issues())


def _new_process() -> None:
    from devops_cli.roadmap.stores.listing_shared import reset_shared_snapshots

    reset_shared_snapshots()


def _valkey_store(tier: ValkeyCacheTier) -> ValkeySnapshotStore:
    from devops_cli.roadmap.stores.listing_shared import ValkeySnapshotStore

    return ValkeySnapshotStore(tier)


def _snapshot(watermark: datetime, *numbers: int, full_at: datetime = STARTED) -> ListingSnapshot:
    """A snapshot of the issues `numbers`, read in full at `full_at`, with `watermark`."""
    records = tuple(
        IssueRecord(
            number=number,
            title=f"Issue {number}",
            url=f"https://github.com/{REPO}/issues/{number}",
            body="Text",
            updated_at=STARTED - timedelta(hours=1),
        )
        for number in numbers
    )
    return ListingSnapshot(
        repo=REPO,
        schema_key=LISTING_SCHEMA_KEY,
        full_at=full_at,
        watermark=watermark,
        issues=records,
    )


def _shared(server: FakeServer) -> tuple[str | None, list[str]]:
    """The watermark of the shared snapshot and the numbers of its issues, the highest first."""
    import json

    reader = FakeValkey(server=server, decode_responses=True)
    meta = reader.hget(SNAPSHOT_KEY, "meta")
    numbers = sorted((f for f in reader.hkeys(SNAPSHOT_KEY) if f != "meta"), key=int, reverse=True)
    return (None if meta is None else json.loads(meta)["watermark"]), numbers


def _keys(server: FakeServer) -> list[str]:
    return sorted(FakeValkey(server=server, decode_responses=True).keys("*"))


def _queries(github_api: GitHubApiFake) -> list[dict[str, str]]:
    return [dict(request.url.params) for request in github_api.sent]


def _summed(otlp: FakeCollector, name: str, *labels: str) -> dict[tuple[str, ...], float]:
    counted: dict[tuple[str, ...], float] = {}
    for attributes, value in otlp.points(name):
        point = tuple(attributes[label] for label in labels)
        counted[point] = counted.get(point, 0) + value
    return counted


def _reads(otlp: FakeCollector) -> dict[tuple[str, ...], float]:
    from devops_cli.telemetry.instruments import BRAIN_READS_TOTAL

    return _summed(otlp, BRAIN_READS_TOTAL.name, "store", "result")


def _writes(otlp: FakeCollector) -> dict[tuple[str, ...], float]:
    from devops_cli.telemetry.instruments import BRAIN_WRITES_TOTAL

    return _summed(otlp, BRAIN_WRITES_TOTAL.name, "store", "result")


def _errors(otlp: FakeCollector) -> dict[tuple[str, ...], float]:
    from devops_cli.telemetry.instruments import VALKEY_CACHE_ERRORS_TOTAL

    return _summed(otlp, VALKEY_CACHE_ERRORS_TOTAL.name, "op", "error")


def _saved(otlp: FakeCollector) -> dict[tuple[str, ...], float]:
    from devops_cli.telemetry.instruments import BRAIN_GITHUB_REQUESTS_SAVED_TOTAL

    return _summed(otlp, BRAIN_GITHUB_REQUESTS_SAVED_TOTAL.name, "store")


def _labels_with_a_name(otlp: FakeCollector) -> list[str]:
    """Each label value of the brain counters that names the repository or holds a number."""
    from devops_cli.telemetry.instruments import (
        BRAIN_GITHUB_REQUESTS_SAVED_TOTAL,
        BRAIN_READS_TOTAL,
        BRAIN_WRITES_TOTAL,
        VALKEY_CACHE_ERRORS_TOTAL,
    )

    names = (
        BRAIN_READS_TOTAL,
        BRAIN_WRITES_TOTAL,
        VALKEY_CACHE_ERRORS_TOTAL,
        BRAIN_GITHUB_REQUESTS_SAVED_TOTAL,
    )
    return [
        f"{label}={value}"
        for name in names
        for attributes, _ in otlp.points(name.name)
        for label, value in attributes.items()
        if label not in {"store", "result", "op", "error"}
        or "/" in value
        or any(character.isdigit() for character in value)
    ]


@pytest.mark.usefixtures("shared_valkey")
def test_a_cold_process_reads_the_shared_snapshot_and_at_most_two_pages(
    github_api: GitHubApiFake, tmp_path: Path, otlp: FakeCollector
) -> None:
    """A process with no local snapshot starts from the shared one, reads one page of changes,
    and counts the 3 pages of the full read that it did not send."""
    github_api.route("GET", FULL, github_json([_issue(n) for n in range(250, 0, -1)]))
    _round(_tiered(tmp_path / "first"))
    _new_process()
    github_api.sent.clear()
    otlp.clear()
    changed = [_issue(n, updated="2026-01-01T10:30:00Z", title=f"new title {n}") for n in (3, 2, 1)]
    github_api.route("GET", _since("2026-01-01T08:59:00Z"), github_json(changed))
    later = STARTED + timedelta(hours=1)

    issues = _round(_tiered(tmp_path / "cold", at=later), at=later)

    kept = FileSnapshotStore(tmp_path / "cold").load(REPO)
    titles = {issue.number: issue.title for issue in issues}
    assert (
        [query.get("since") for query in _queries(github_api)],
        len(issues),
        [titles[n] for n in (1, 2, 3)],
        None if kept is None else len(kept.issues),
        _saved(otlp),
        _reads(otlp),
        _labels_with_a_name(otlp),
    ) == (
        ["2026-01-01T08:59:00Z"],
        250,
        ["new title 1", "new title 2", "new title 3"],
        250,
        {("snapshot",): 3.0},
        {("snapshot", "shared"): 1.0},
        [],
    )


def test_the_newer_copy_of_the_two_tiers_gives_the_watermark(
    github_api: GitHubApiFake, tmp_path: Path, shared_valkey: ValkeyCacheTier
) -> None:
    """The local copy has the watermark 09:00 and the shared copy 10:00: the read starts at 10:00."""
    FileSnapshotStore(tmp_path).save(_snapshot(STARTED - timedelta(hours=1), 2, 1))
    _valkey_store(shared_valkey).save(_snapshot(STARTED, 3, 2, 1))
    github_api.route("GET", _since("2026-01-01T10:00:00Z"), github_json([]))
    later = STARTED + timedelta(hours=1)

    numbers = [issue.number for issue in _round(_tiered(tmp_path, at=later), at=later)]

    assert ([query.get("since") for query in _queries(github_api)], numbers) == (
        ["2026-01-01T10:00:00Z"],
        [3, 2, 1],
    )


def test_a_round_with_the_shared_tier_down_reads_the_local_file(
    github_api: GitHubApiFake,
    tmp_path: Path,
    valkey_server: FakeServer,
    shared_valkey: ValkeyCacheTier,
    otlp: FakeCollector,
) -> None:
    """T2: the round reads the changes since the local watermark and keeps the new local file;
    one command reaches Valkey, and the round reads no visibility."""
    FileSnapshotStore(tmp_path).save(_snapshot(STARTED - timedelta(minutes=1), 2, 1))
    github_api.route(
        "GET",
        _since("2026-01-01T09:59:00Z"),
        github_json([_issue(3, updated="2026-01-01T10:30:00Z")]),
    )
    asked: list[str] = []

    def is_public(repo: str) -> bool:
        asked.append(repo)
        return True

    valkey_server.connected = False
    later = STARTED + timedelta(hours=1)
    numbers = [i.number for i in _round(_tiered(tmp_path, at=later, is_public=is_public), at=later)]
    kept = FileSnapshotStore(tmp_path).load(REPO)

    assert (
        numbers,
        None if kept is None else [i.number for i in kept.issues],
        asked,
        _reads(otlp),
        _writes(otlp),
        _errors(otlp),
    ) == (
        [3, 2, 1],
        [3, 2, 1],
        [],
        {("snapshot", "fallback"): 1.0},
        {("snapshot", "skipped"): 1.0},
        {("hget", "connection"): 1.0, ("hget", "open"): 1.0},
    )


def test_a_trial_after_the_cooldown_lets_the_newer_snapshot_replace_the_older(
    tmp_path: Path,
    valkey_server: FakeServer,
    shared_valkey: ValkeyCacheTier,
    clock: ClockFake,
) -> None:
    """T4: the breaker is open; after the cooldown the save is the trial, which closes it, and
    the snapshot of watermark 10:00 replaces the one of 09:00."""
    from devops_cli.config.defaults import DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS

    _valkey_store(shared_valkey).save(_snapshot(STARTED - timedelta(hours=1), 1))
    valkey_server.connected = False
    tiered = _tiered(tmp_path)
    tiered.load(REPO)
    valkey_server.connected = True
    in_the_cooldown = (shared_valkey.is_open, _shared(valkey_server)[0])
    clock.shift(DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS)

    tiered.save(_snapshot(STARTED, 2, 1))

    assert (in_the_cooldown, shared_valkey.is_open, _shared(valkey_server)) == (
        (True, "2026-01-01T09:00:00Z"),
        False,
        ("2026-01-01T10:00:00Z", ["2", "1"]),
    )


def _between_watch_and_exec(action: Callable[[], None]) -> Callable[[tuple[Any, ...]], None]:
    """An `after_command` hook of the fake that runs `action` once, after the read of the first
    WATCH transaction and before its EXEC."""
    watched: list[tuple[Any, ...]] = []

    def hook(command: tuple[Any, ...]) -> None:
        if command[0] == "WATCH":
            watched.append(command)
        elif command[0] == "HGET" and len(watched) == 1:
            watched.append(command)
            action()

    return hook


def test_an_older_writer_loses_its_watch_transaction(
    tmp_path: Path, valkey_server: FakeServer, shared_valkey: ValkeyCacheTier, otlp: FakeCollector
) -> None:
    """T4: a writer of watermark 10:15 reads the shared watermark 10:00, and another client
    writes 10:30 before its EXEC. Its transaction writes nothing, it does not try again, and it
    leaves no temporary key."""
    _valkey_store(shared_valkey).save(_snapshot(STARTED, 1))
    other = _valkey_store(ValkeyCacheTier(valkey_client_on(valkey_server)))
    racing = ValkeyCacheTier(
        valkey_client_on(
            valkey_server,
            after_command=_between_watch_and_exec(
                lambda: other.save(_snapshot(STARTED + timedelta(minutes=30), 3, 1))
            ),
        )
    )
    otlp.clear()

    _tiered(tmp_path, shared=lambda: _valkey_store(racing)).save(
        _snapshot(STARTED + timedelta(minutes=15), 2, 1)
    )

    assert (_shared(valkey_server), _keys(valkey_server), _writes(otlp)) == (
        ("2026-01-01T10:30:00Z", ["3", "1"]),
        [SNAPSHOT_KEY],
        {("snapshot", "older"): 1.0, ("snapshot", "shared"): 1.0},
    )


@pytest.mark.usefixtures("shared_valkey")
def test_an_older_watermark_does_not_replace_the_shared_snapshot(
    tmp_path: Path, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """The shared snapshot of 10:00 keeps its watermark and records; the local file takes 09:00."""
    _tiered(tmp_path / "newer").save(_snapshot(STARTED, 2, 1))
    otlp.clear()

    _tiered(tmp_path / "older").save(_snapshot(STARTED - timedelta(hours=1), 1))

    kept = FileSnapshotStore(tmp_path / "older").load(REPO)
    assert (
        _shared(valkey_server),
        None if kept is None else kept.watermark,
        _writes(otlp),
    ) == (
        ("2026-01-01T10:00:00Z", ["2", "1"]),
        STARTED - timedelta(hours=1),
        {("snapshot", "older"): 1.0},
    )


@pytest.mark.usefixtures("shared_valkey")
def test_a_full_read_replaces_the_shared_snapshot_whole(
    github_api: GitHubApiFake, tmp_path: Path, valkey_server: FakeServer
) -> None:
    """Issue 2 left the repository: the full read lists 1 and 3, and the shared snapshot holds
    only them, with no temporary key left."""
    github_api.route("GET", FULL, github_json([_issue(3), _issue(2), _issue(1)]))
    _round(_tiered(tmp_path))
    github_api.route(
        "GET", FULL, github_json([_issue(3, updated="2026-01-01T09:30:00Z"), _issue(1)])
    )
    later = STARTED + timedelta(hours=1)

    _round(_tiered(tmp_path, at=later), at=later, full=True)

    assert (_shared(valkey_server), _keys(valkey_server)) == (
        ("2026-01-01T09:29:00Z", ["3", "1"]),
        [SNAPSHOT_KEY],
    )


@pytest.mark.usefixtures("shared_valkey")
def test_no_key_of_a_private_repository_is_written(
    github_api: GitHubApiFake, tmp_path: Path, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A round for a private repository and a round whose visibility read fails write no key
    and use no shared copy; each counts `private`. A private answer is kept for the round; a
    failed read is not, so the save reads the visibility again."""
    from devops_cli.roadmap.stores.listing_shared import repository_is_public

    private = RecordedGh({"isPrivate": {"data": {"repository": {"isPrivate": True}}}})
    failing = RecordedGh({"isPrivate": (1, "HTTP 502: Bad Gateway")})
    github_api.route("GET", FULL, github_json([_issue(2), _issue(1)]))
    github_api.route("GET", _since("2026-01-01T08:59:00Z"), github_json([]))

    _round(_tiered(tmp_path, is_public=lambda repo: repository_is_public(repo, runner=private)))
    _new_process()
    later = STARTED + timedelta(hours=1)
    _round(
        _tiered(
            tmp_path, at=later, is_public=lambda repo: repository_is_public(repo, runner=failing)
        ),
        at=later,
    )

    assert (
        _keys(valkey_server),
        len(private.calls),
        len(failing.calls),
        _reads(otlp),
        _writes(otlp),
    ) == (
        [],
        1,
        2,
        {("snapshot", "private"): 2.0},
        {("snapshot", "private"): 2.0},
    )


def test_no_visibility_read_without_the_shared_tier(
    github_api: GitHubApiFake,
    tmp_path: Path,
    valkey_server: FakeServer,
    shared_valkey: ValkeyCacheTier,
) -> None:
    from devops_cli.roadmap.stores.listing_shared import repository_is_public

    runner = RecordedGh({})
    github_api.route("GET", FULL, github_json([_issue(1)]))
    valkey_server.connected = False

    _round(_tiered(tmp_path, is_public=lambda repo: repository_is_public(repo, runner=runner)))

    assert runner.calls == []


def test_a_shared_load_past_its_budget_falls_back(
    tmp_path: Path,
    valkey_server: FakeServer,
    shared_valkey: ValkeyCacheTier,
    clock: ClockFake,
    otlp: FakeCollector,
) -> None:
    """The load of a shared snapshot of 1,200 records stops after the second `HSCAN`, and the
    reader takes the local snapshot."""
    local = _snapshot(STARTED - timedelta(hours=1), 1)
    FileSnapshotStore(tmp_path).save(local)
    _valkey_store(shared_valkey).save(_snapshot(STARTED, *range(1200, 0, -1)))
    scans: list[tuple[Any, ...]] = []

    def slow(command: tuple[Any, ...]) -> None:
        if command[0] == "HSCAN":
            scans.append(command)
            if len(scans) == 2:
                clock.shift(21)

    slow_tier = ValkeyCacheTier(valkey_client_on(valkey_server, after_command=slow))
    otlp.clear()

    loaded = _tiered(tmp_path, shared=lambda: _valkey_store(slow_tier)).load(REPO)

    assert (loaded, len(scans), _errors(otlp), _reads(otlp)) == (
        local,
        2,
        {("hscan", "budget"): 1.0},
        {("snapshot", "fallback"): 1.0},
    )


def _meta(server: FakeServer) -> bytes | None:
    """The `meta` field of the shared snapshot as Valkey holds it."""
    value: bytes | None = FakeValkey(server=server).hget(SNAPSHOT_KEY, "meta")
    return value


def test_a_save_of_the_records_that_the_shared_copy_holds_writes_no_record(
    tmp_path: Path, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """Two lanes of one process hold the same 1,200 records and watermark, with full reads at
    08:00 and 09:00, and a new process holds them too. After the first save of each lane, a save
    sends no record and no transaction, keeps `meta` as it is, and counts `unchanged`."""
    sent: list[str] = []
    lanes = _valkey_store(
        ValkeyCacheTier(
            valkey_client_on(valkey_server, after_command=lambda command: sent.append(command[0]))
        )
    )
    records = range(1200, 0, -1)
    older = _snapshot(STARTED, *records, full_at=STARTED - timedelta(hours=2))
    newer = _snapshot(STARTED, *records, full_at=STARTED - timedelta(hours=1))
    lane_a = _tiered(tmp_path / "a", shared=lambda: lanes)
    lane_b = _tiered(tmp_path / "b", shared=lambda: lanes)
    lane_a.save(older)
    lane_b.save(newer)
    first = _meta(valkey_server)
    sent.clear()
    otlp.clear()

    for _ in range(2):
        lane_a.save(older)
        lane_b.save(newer)
    new_process = _valkey_store(ValkeyCacheTier(valkey_client_on(valkey_server)))
    _tiered(tmp_path / "c", shared=lambda: new_process).save(older)

    assert (set(sent), _meta(valkey_server) == first, _writes(otlp), _keys(valkey_server)) == (
        {"HGET", "EXPIRE"},
        True,
        {("snapshot", "unchanged"): 5.0},
        [SNAPSHOT_KEY],
    )


def test_a_new_meta_of_the_same_records_during_a_load_keeps_the_shared_copy(
    tmp_path: Path, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A writer saves the same 1,200 records with a newer full read while a cold process scans
    them. The reader still takes the shared copy, because the records that it read are the ones
    that the new `meta` names."""
    writer = _valkey_store(ValkeyCacheTier(valkey_client_on(valkey_server)))
    records = range(1200, 0, -1)
    writer.save(_snapshot(STARTED, *records, full_at=STARTED - timedelta(hours=2)))

    def write_during_the_scan(command: tuple[Any, ...]) -> None:
        if command[0] == "HSCAN" and command[2] == 0:
            writer.save(_snapshot(STARTED, *records, full_at=STARTED - timedelta(hours=1)))

    reader = _valkey_store(
        ValkeyCacheTier(valkey_client_on(valkey_server, after_command=write_during_the_scan))
    )
    otlp.clear()

    loaded = _tiered(tmp_path, shared=lambda: reader).load(REPO)

    assert (None if loaded is None else len(loaded.issues), _reads(otlp)) == (
        1200,
        {("snapshot", "shared"): 1.0},
    )


def _naive_meta(server: FakeServer) -> None:
    """Write the times of `meta` with no UTC offset."""
    import json

    writer = FakeValkey(server=server)
    raw = writer.hget(SNAPSHOT_KEY, "meta")
    assert raw is not None
    meta = json.loads(raw)
    meta |= {"full_at": "2026-01-01T09:00:00", "watermark": "2026-01-01T10:00:00"}
    writer.hset(SNAPSHOT_KEY, "meta", json.dumps(meta))


def _expanding_record(server: FakeServer) -> None:
    """Write a record whose zlib value expands to more than 1 MiB of JSON."""
    import zlib

    from devops_cli.config.defaults import DEFAULT_BRAIN_VALUE_MAX_BYTES

    record = IssueRecord(
        number=2,
        title="Issue 2",
        url=f"https://github.com/{REPO}/issues/2",
        body="x" * DEFAULT_BRAIN_VALUE_MAX_BYTES,
        updated_at=STARTED,
    )
    FakeValkey(server=server).hset(
        SNAPSHOT_KEY, "2", zlib.compress(record.model_dump_json().encode())
    )


def _no_change(server: FakeServer) -> None:
    """Leave the shared copy as the writer wrote it."""


@pytest.mark.parametrize(
    ("spoil", "naive_record"),
    [
        pytest.param(_naive_meta, False, id="naive-meta"),
        pytest.param(_no_change, True, id="naive-record"),
        pytest.param(_expanding_record, False, id="record-past-the-bound"),
    ],
)
def test_a_shared_copy_with_a_time_with_no_offset_or_a_record_past_the_bound_is_a_miss(
    tmp_path: Path,
    valkey_server: FakeServer,
    shared_valkey: ValkeyCacheTier,
    spoil: Callable[[FakeServer], None],
    naive_record: bool,
) -> None:
    """The shared copy is newer than the local one, but its `meta` or a record holds a time with
    no UTC offset, or a record expands past 1 MiB. The load takes the local copy, and the next
    save replaces the shared copy."""
    local = _snapshot(STARTED - timedelta(hours=1), 1)
    FileSnapshotStore(tmp_path).save(local)
    shared = _snapshot(STARTED, 2, 1)
    if naive_record:
        naive_time = STARTED.replace(tzinfo=None) - timedelta(hours=1)
        naive = shared.issues[0].model_copy(update={"updated_at": naive_time})
        shared = shared.model_copy(update={"issues": (naive, *shared.issues[1:])})
    _valkey_store(shared_valkey).save(shared)
    spoil(valkey_server)

    loaded = _tiered(tmp_path).load(REPO)
    _tiered(tmp_path).save(_snapshot(STARTED + timedelta(hours=1), 3, 2, 1))

    assert (loaded, _shared(valkey_server)) == (local, ("2026-01-01T11:00:00Z", ["3", "2", "1"]))


@pytest.mark.usefixtures("shared_valkey")
def test_a_repository_that_became_private_leaves_the_shared_tier(
    github_api: GitHubApiFake, tmp_path: Path, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A round of a public repository writes its shared copy. A round after the repository
    became private removes the key, uses no shared copy and counts `removed`."""
    github_api.route("GET", FULL, github_json([_issue(2), _issue(1)]))
    github_api.route("GET", _since("2026-01-01T08:59:00Z"), github_json([]))
    _round(_tiered(tmp_path))
    public_round = _keys(valkey_server)
    _new_process()
    otlp.clear()
    later = STARTED + timedelta(hours=1)

    _round(_tiered(tmp_path, at=later, is_public=lambda repo: False), at=later)

    assert (public_round, _keys(valkey_server), _reads(otlp), _writes(otlp)) == (
        [SNAPSHOT_KEY],
        [],
        {("snapshot", "private"): 1.0},
        {("snapshot", "removed"): 1.0, ("snapshot", "private"): 1.0},
    )


@pytest.mark.usefixtures("shared_valkey")
def test_one_shared_key_and_one_visibility_read_hold_a_repository_in_each_spelling(
    tmp_path: Path, valkey_server: FakeServer
) -> None:
    """GitHub names ignore case: a save as `Dan-Petty/DevOps-CLI` and a load as
    `dan-petty/devops-cli` use one key, and the visibility of the two is read once."""
    from devops_cli.roadmap.stores.listing_shared import repository_is_public

    spelled = "Dan-Petty/DevOps-CLI"
    runner = RecordedGh({"isPrivate": {"data": {"repository": {"isPrivate": False}}}})
    _tiered(tmp_path / "a").save(_snapshot(STARTED, 2, 1).model_copy(update={"repo": spelled}))
    _new_process()

    loaded = _tiered(tmp_path / "b").load(REPO)
    answers = (
        repository_is_public(spelled, runner=runner),
        repository_is_public(REPO, runner=runner),
    )

    assert (
        _keys(valkey_server),
        None if loaded is None else [issue.number for issue in loaded.issues],
        answers,
        len(runner.calls),
    ) == ([SNAPSHOT_KEY], [2, 1], (True, True), 1)


@pytest.mark.usefixtures("shared_valkey")
def test_a_load_counts_the_tier_that_gave_the_snapshot(tmp_path: Path, otlp: FakeCollector) -> None:
    """With no copy in either tier the load counts `source`. With the same watermark in both
    tiers, the local copy wins and the load counts `local`, not `source`."""
    snapshot = _snapshot(STARTED, 2, 1)
    empty = _tiered(tmp_path).load(REPO)
    _tiered(tmp_path).save(snapshot)

    loaded = _tiered(tmp_path).load(REPO)

    assert (empty, loaded, _reads(otlp)) == (
        None,
        snapshot,
        {("snapshot", "source"): 1.0, ("snapshot", "local"): 1.0},
    )


def test_the_lanes_of_one_process_scan_the_records_of_a_shared_copy_once(
    tmp_path: Path, valkey_server: FakeServer
) -> None:
    """Lane A of a process saves a newer watermark. Lane B, whose local copy is older, takes the
    shared copy that the store of the process holds: it reads `meta` and sends no `HSCAN`."""
    sent: list[str] = []
    store = _valkey_store(
        ValkeyCacheTier(
            valkey_client_on(valkey_server, after_command=lambda command: sent.append(command[0]))
        )
    )
    lane_a = _tiered(tmp_path / "a", shared=lambda: store)
    lane_b = _tiered(tmp_path / "b", shared=lambda: store)
    lane_b.save(_snapshot(STARTED - timedelta(hours=1), 2, 1))
    lane_a.save(_snapshot(STARTED, 3, 2, 1))
    sent.clear()

    loaded = lane_b.load(REPO)

    assert (
        None if loaded is None else ([issue.number for issue in loaded.issues], loaded.watermark),
        sent,
    ) == (([3, 2, 1], STARTED), ["HGET"])
