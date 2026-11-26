"""The keys of the brain index of one repository in `valkey-roadmap` (#4676).

The index holds one hash for the item of a check, one for its tool and one for each reference,
each with a TTL of 45 days, the audit stream `brain-events` and the watermark of the sync. The
keys of one item and its stream entry go in one MULTI/EXEC, the entry of the newer check stays,
and each read fails soft. The store is the in-memory Valkey: a second client reads what the index
wrote, and the client of the index records each MULTI/EXEC block that it sends.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from fakeredis import FakeServer, FakeValkey

from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.brain_entries import (
    BrainEntry,
    checked_entry,
    reference_key_id,
    tool_key_id,
)
from devops_cli.roadmap.brain_index import BrainIndex, Related, Watermark, Written
from devops_cli.roadmap.stores.store import GitHubState, Verdict
from tests.support.fakes.valkey import valkey_client_on

if TYPE_CHECKING:
    from devops_cli.valkey.client import ValkeyClient

REPO = RepoRef("Acme/Widgets")
TTL = 3_888_000
CHECKED_AT = datetime(2026, 11, 26, 5, 10, 18, tzinfo=UTC)
TOOL_ID = "github.com/acme/widget-kit"
TOOL_URL = "https://github.com/acme/widget-kit"
FRAMES = "https://github.com/acme/frames"
PANELS = "https://github.com/acme/panels"
ITEM_KEY = "roadmap:v1:brain-item:acme/widgets:7"
TOOL_KEY = f"roadmap:v1:brain-tool:acme/widgets:{tool_key_id(TOOL_ID)}"
FRAMES_KEY = f"roadmap:v1:brain-ref:acme/widgets:{reference_key_id(FRAMES)}"
PANELS_KEY = f"roadmap:v1:brain-ref:acme/widgets:{reference_key_id(PANELS)}"
EVENTS_KEY = "roadmap:v1:brain-events:acme/widgets"
SYNC_KEY = "roadmap:v1:brain-sync:acme/widgets"


def _entry(**changes: Any) -> BrainEntry:
    """The entry of a `covers` check of item 7 with a tool and two references."""
    fields: dict[str, Any] = {
        "number": 7,
        "state": GitHubState.OPEN,
        "verdict": Verdict.COVERS,
        "checked_at": CHECKED_AT,
        "body_hash": "b" * 64,
        "adr_hash": "a" * 64,
        "tool_id": TOOL_ID,
        "tool_url": TOOL_URL,
        "tool_name": "Widget Kit",
        "refs": (FRAMES, PANELS),
        "uses": ("item:3", "tool:0123456789abcdef"),
    }
    return BrainEntry(**(fields | changes))


RELATED = Related(near=(9, 3), tool_items=(3, 7, 9), reference_items={FRAMES: (7,), PANELS: (3, 7)})


def _tier(client: ValkeyClient) -> Any:
    """The tier of the roadmap state over `client`."""
    from devops_cli.valkey.cache import ValkeyCacheTier

    return ValkeyCacheTier(client)


@pytest.fixture
def transactions() -> list[list[list[str]]]:
    """The commands of each MULTI/EXEC block that the client of the index sent."""
    return []


@pytest.fixture
def index(valkey_server: FakeServer, transactions: list[list[list[str]]]) -> Iterator[BrainIndex]:
    """The index of `REPO` over the in-memory Valkey."""
    client = valkey_client_on(valkey_server, transactions=transactions)
    yield BrainIndex(_tier(client), REPO)
    client.close()


@pytest.fixture
def reader(valkey_server: FakeServer) -> FakeValkey:
    """A second client of the store, which reads what the index wrote."""
    return FakeValkey(server=valkey_server, decode_responses=True)


def test_the_item_hash_holds_each_field_of_the_check_and_expires_in_45_days(
    index: BrainIndex, reader: FakeValkey
) -> None:
    """A check whose record names 4 references keeps 3. The item hash holds the verdict, the tool
    id, the 3 reference ids, the near items, the time and the hashes of the check, the state, the
    used entries and the schema, and `TTL` gives 3888000."""
    links = " ".join(
        f"https://github.com/acme/{name}/blob/0123abc/a.py#L1"
        for name in ("frames", "panels", "grids", "tiles")
    )
    block = (
        "<!-- devops-roadmap-alternatives:start -->\n"
        "Alternatives check of 2026-11-26: covers.\n"
        f"Tool: Widget Kit ({TOOL_URL}), MIT License, last activity 2026-10-12, maintained.\n"
        "<!-- devops-roadmap-alternatives:end -->"
    )
    entry = checked_entry(
        7,
        GitHubState.OPEN,
        block,
        {
            "alternatives.verdict": "covers",
            "alternatives.checked_at": CHECKED_AT.isoformat(),
            "alternatives.body_hash": "b" * 64,
            "alternatives.adr_hash": "a" * 64,
            "alternatives.tool": TOOL_URL,
            "alternatives.tool_id": TOOL_ID,
            "alternatives.refs": links,
            "alternatives.brain_used": "item:3",
        },
    )
    assert entry is not None

    written = index.write(entry, Related(near=(9, 3, 11, 12, 13)))

    reference_ids = " ".join(
        reference_key_id(f"https://github.com/acme/{name}")
        for name in ("frames", "panels", "grids")
    )
    assert (written, reader.hgetall(ITEM_KEY), reader.ttl(ITEM_KEY)) == (
        Written.NEW,
        {
            "schema": "1",
            "verdict": "covers",
            "tool_id": TOOL_ID,
            "refs": reference_ids,
            "near": "9 3 11 12 13",
            "checked_at": "2026-11-26T05:10:18+00:00",
            "body_hash": "b" * 64,
            "adr_hash": "a" * 64,
            "state": "open",
            "uses": "item:3",
        },
        TTL,
    )


def test_the_keys_of_one_item_and_its_event_go_in_one_transaction(
    index: BrainIndex, reader: FakeValkey, transactions: list[list[list[str]]]
) -> None:
    """One MULTI/EXEC holds the item hash, the tool hash, each reference hash and one entry of
    `brain-events` with MAXLEN 10000. The stream holds that one entry."""
    index.write(_entry(), RELATED)

    checked_at = "2026-11-26T05:10:18+00:00"
    item_fields = [
        *("schema", "1", "verdict", "covers", "tool_id", TOOL_ID),
        *("refs", f"{reference_key_id(FRAMES)} {reference_key_id(PANELS)}"),
        *("near", "9 3", "checked_at", checked_at, "body_hash", "b" * 64),
        *("adr_hash", "a" * 64, "state", "open"),
        *("uses", "item:3 tool:0123456789abcdef"),
    ]
    tool_fields = [
        *("schema", "1", "id", TOOL_ID, "url", TOOL_URL, "name", "Widget Kit"),
        *("checked_at", checked_at, "items", "3 7 9"),
    ]
    event = ["item", "7", "verdict", "covers", "tool_id", TOOL_ID, "checked_at", checked_at]
    assert transactions == [
        [
            ["MULTI"],
            ["HSET", ITEM_KEY, *item_fields],
            ["EXPIRE", ITEM_KEY, str(TTL)],
            ["HSET", TOOL_KEY, *tool_fields],
            ["EXPIRE", TOOL_KEY, str(TTL)],
            ["HSET", FRAMES_KEY, "schema", "1", "url", FRAMES, "checked_at", checked_at]
            + ["items", "7"],
            ["EXPIRE", FRAMES_KEY, str(TTL)],
            ["HSET", PANELS_KEY, "schema", "1", "url", PANELS, "checked_at", checked_at]
            + ["items", "3 7"],
            ["EXPIRE", PANELS_KEY, str(TTL)],
            ["XADD", EVENTS_KEY, "MAXLEN", "~", "10000", "*", *event],
            ["EXPIRE", EVENTS_KEY, str(TTL)],
            ["EXEC"],
        ]
    ]
    assert [fields for _, fields in reader.xrange(EVENTS_KEY)] == [
        dict(zip(*[iter(event)] * 2, strict=True))
    ]


def test_a_check_with_no_tool_and_no_reference_writes_its_item_and_its_event_only(
    index: BrainIndex, reader: FakeValkey
) -> None:
    """A verdict `none` names no tool: the index gets the item hash and the stream, and no tool
    or reference hash."""
    entry = _entry(verdict=Verdict.NONE, tool_id="", tool_url="", tool_name="", refs=(), uses=())

    index.write(entry, Related())

    assert (sorted(reader.keys("*")), reader.hget(ITEM_KEY, "verdict")) == (
        [EVENTS_KEY, ITEM_KEY],
        "none",
    )


def test_the_block_with_the_newer_check_replaces_an_older_entry(
    index: BrainIndex, reader: FakeValkey
) -> None:
    """The index holds an entry with an older `checked_at`. The block gives a newer `checked_at`
    and another `body_hash`: the write replaces the entry, which then holds both."""
    newer = CHECKED_AT + timedelta(days=30)
    index.write(_entry(), RELATED)

    written = index.write(_entry(checked_at=newer, body_hash="c" * 64), RELATED)

    assert (written, reader.hmget(ITEM_KEY, "checked_at", "body_hash")) == (
        Written.REPLACED,
        [newer.isoformat(), "c" * 64],
    )


def test_a_late_write_of_an_older_block_keeps_the_newer_entry(
    index: BrainIndex, reader: FakeValkey, transactions: list[list[list[str]]]
) -> None:
    """A copy of the issue from before its last check comes after the entry of that check: the
    index keeps the entry of the newer check and sends no second transaction."""
    newer = CHECKED_AT + timedelta(days=30)
    index.write(_entry(checked_at=newer, body_hash="c" * 64), RELATED)

    written = index.write(_entry(), RELATED)

    assert (
        written,
        reader.hmget(ITEM_KEY, "checked_at", "body_hash"),
        len(transactions),
        reader.xlen(EVENTS_KEY),
    ) == (Written.KEPT, [newer.isoformat(), "c" * 64], 1, 1)


def test_each_key_has_a_ttl_of_45_days_and_the_watermark_has_none_and_one_writer(
    index: BrainIndex, reader: FakeValkey, transactions: list[list[list[str]]]
) -> None:
    """A scan of the store after the write of one item and of the watermark: the item, tool and
    reference hashes and the stream expire in 45 days, and the watermark key has no TTL. No
    transaction of an item names the watermark key: only the write of the watermark does. Each
    key starts with `roadmap:v1:brain-`, the key pattern of the ACL users `brain` and `agent`."""
    index.write(_entry(), RELATED)
    index.advance(Watermark(changed=CHECKED_AT, number=7, synced_at=CHECKED_AT))

    ttls = {key: reader.ttl(key) for key in reader.scan_iter("*")}
    in_transactions = {command[1] for block in transactions for command in block[1:-1]}
    assert (ttls, SYNC_KEY in in_transactions) == (
        {
            ITEM_KEY: TTL,
            TOOL_KEY: TTL,
            FRAMES_KEY: TTL,
            PANELS_KEY: TTL,
            EVENTS_KEY: TTL,
            SYNC_KEY: -1,
        },
        False,
    )


def test_the_scan_of_one_repository_gives_no_key_of_a_longer_name(
    valkey_server: FakeServer, valkey_client: ValkeyClient
) -> None:
    """The index holds the keys of `o/n` and of `o/nn`. The scan of `roadmap:v1:brain-item:o/n:*`
    gives the keys of `o/n` only."""
    tier = _tier(valkey_client)
    short, longer = BrainIndex(tier, RepoRef("o/n")), BrainIndex(tier, RepoRef("o/nn"))
    short.write(_entry(number=1), Related())
    longer.write(_entry(number=1), Related())
    longer.write(_entry(number=2), Related())

    assert (short.item_keys(), longer.item_keys()) == (
        ["roadmap:v1:brain-item:o/n:1"],
        ["roadmap:v1:brain-item:o/nn:1", "roadmap:v1:brain-item:o/nn:2"],
    )


def test_the_watermark_comes_back_as_the_sync_wrote_it(index: BrainIndex) -> None:
    """The store holds no watermark before the first sync. A write of the sync time alone keeps
    the place that an earlier write gave."""
    before = index.watermark()
    index.advance(Watermark(changed=CHECKED_AT, number=7, synced_at=CHECKED_AT))
    later = CHECKED_AT + timedelta(minutes=2)
    index.advance(Watermark(synced_at=later))

    assert (before, index.watermark()) == (
        Watermark(),
        Watermark(changed=CHECKED_AT, number=7, synced_at=later),
    )


def test_a_store_that_does_not_answer_gives_no_watermark_no_keys_and_no_write(
    index: BrainIndex, valkey_server: FakeServer, reader: FakeValkey
) -> None:
    """While the store is down, each read gives None and each write does not occur, with no
    error."""
    valkey_server.connected = False
    results = (
        index.watermark(),
        index.write(_entry(), RELATED),
        index.advance(Watermark(synced_at=CHECKED_AT)),
        index.item_keys(),
    )
    valkey_server.connected = True

    assert (results, reader.keys("*")) == ((None, None, False, None), [])
