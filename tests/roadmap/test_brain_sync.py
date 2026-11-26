"""`brain-sync`, the step of an alternatives round that copies the checks of the listing snapshot
into the brain index (#4676).

The step reads only the issues of the snapshot: it sends no GitHub request. It copies each issue
that changed since its watermark, at most a bound of them in one round, and observes three
instruments. A round whose store is down or not configured finishes and counts `fallback`. The
check of an item that the index held no entry for counts one first read.

The store is the in-memory Valkey, the roadmap of a round is the in-memory store, pydantic-ai's
`FunctionModel` answers the model request of a check, and Firecrawl is answered at the HTTP edge.
The counters are read on the OTLP fake.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from fakeredis import FakeServer, FakeValkey
from pydantic_ai.messages import ModelMessage, ToolReturnPart

from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_URL
from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.alternatives import (
    AlternativesReply,
    AlternativesWriter,
    plan_alternatives,
)
from devops_cli.roadmap.brain_index import BrainIndex, Watermark
from devops_cli.roadmap.brain_sync import BrainSync, sync_alternatives_round, sync_brain_index
from devops_cli.roadmap.stores.store import (
    AlternativesRecordKey,
    GitHubState,
    IssueRecord,
    ItemField,
    Verdict,
)
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.fakes.valkey import valkey_client_on
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from devops_cli.valkey.cache import ValkeyCacheTier
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.http import WebFake

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "acme/widgets"
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
CHECKED_AT = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)
TOOL_URL = "https://github.com/acme/widget-kit"
TOOL_ID = "github.com/acme/widget-kit"
EVENTS_KEY = "roadmap:v1:brain-events:acme/widgets"


def _item_key(number: int, repo: str = REPO) -> str:
    return f"roadmap:v1:brain-item:{repo}:{number}"


def _issue(
    number: int,
    *,
    updated_at: datetime,
    checked_at: datetime | None = CHECKED_AT,
    state: GitHubState = GitHubState.OPEN,
) -> IssueRecord:
    """Issue `number` of the snapshot, last changed at `updated_at`. With `checked_at`, it holds
    the block and the record of a `covers` check of that time; with None, it holds no check."""
    body, record = "The item needs widgets.", {}
    if checked_at is not None:
        body += (
            "\n\n<!-- devops-roadmap-alternatives:start -->\n"
            f"Alternatives check of {checked_at.date().isoformat()}: covers.\n"
            f"Tool: Widget Kit ({TOOL_URL}), MIT License, last activity 2026-10-12, maintained.\n"
            "<!-- devops-roadmap-alternatives:end -->"
        )
        record = {
            AlternativesRecordKey.CHECKED_AT: checked_at.isoformat(),
            AlternativesRecordKey.BODY_HASH: f"{number:064x}",
            AlternativesRecordKey.VERDICT: "covers",
            AlternativesRecordKey.TOOL: TOOL_URL,
            AlternativesRecordKey.TOOL_ID: TOOL_ID,
        }
    return IssueRecord(
        number=number,
        title=f"Build widget {number}",
        url=f"https://github.com/{REPO}/issues/{number}",
        body=body,
        state=state,
        updated_at=updated_at,
        job_record=record,
    )


def _tier(client: Any) -> Any:
    """The tier of the roadmap state over `client`."""
    from devops_cli.valkey.cache import ValkeyCacheTier

    return ValkeyCacheTier(client)


@pytest.fixture
def tier(valkey_server: FakeServer) -> Iterator[Any]:
    """The tier of the roadmap state over the in-memory Valkey."""
    client = valkey_client_on(valkey_server)
    yield _tier(client)
    client.close()


@pytest.fixture
def reader(valkey_server: FakeServer) -> FakeValkey:
    """A second client of the store, which reads what the sync wrote."""
    return FakeValkey(server=valkey_server, decode_responses=True)


def _summed(otlp: FakeCollector, name: str) -> dict[tuple[str, ...], float]:
    """The sum of each series of the counter `name`, by its attribute values in name order."""
    counted: dict[tuple[str, ...], float] = {}
    for attributes, value in otlp.points(name):
        point = tuple(str(attributes[label]) for label in sorted(attributes))
        counted[point] = counted.get(point, 0) + value
    return counted


def _last(otlp: FakeCollector, name: str) -> tuple[dict[str, Any], float] | None:
    """The last point of the gauge `name`."""
    points = otlp.points(name)
    return points[-1] if points else None


# ── The copy of the snapshot ──────────────────────────────────────────────────


def test_a_sync_of_three_changed_issues_writes_three_item_hashes_with_no_github_request(
    tier: Any, reader: FakeValkey, github_api: GitHubApiFake
) -> None:
    """The snapshot holds 3 changed issues and the index is empty: the sync writes 3 item hashes,
    and GitHub gets no request."""
    issues = [_issue(number, updated_at=NOW - timedelta(minutes=number)) for number in (1, 2, 3)]

    result = sync_brain_index(REPO, issues, tier=tier, now=NOW)

    assert (
        result,
        sorted(reader.scan_iter("roadmap:v1:brain-item:*")),
        github_api.requested,
    ) == (BrainSync(copied=3, entries=3), [_item_key(1), _item_key(2), _item_key(3)], [])


def test_a_sync_after_an_outage_copies_the_three_issues_that_changed_in_it(
    tier: Any, reader: FakeValkey
) -> None:
    """The watermark is older than the `updated_at` of 3 issues: one got a new check, one was
    closed and one got a comment. The sync copies exactly these 3, and the watermark moves to the
    last of them. The issue that did not change gets no second write."""
    first = NOW - timedelta(hours=6)
    held = [_issue(number, updated_at=first - timedelta(minutes=number)) for number in (1, 2, 3, 4)]
    sync_brain_index(REPO, held, tier=tier, now=first)
    rechecked = NOW - timedelta(hours=2)
    changed = [
        _issue(1, updated_at=NOW - timedelta(hours=3), checked_at=rechecked),
        _issue(2, updated_at=NOW - timedelta(hours=2), state=GitHubState.CLOSED),
        _issue(3, updated_at=NOW - timedelta(hours=1)),
        held[3],
    ]

    result = sync_brain_index(REPO, changed, tier=tier, now=NOW)

    assert (
        result.copied,
        reader.xlen(EVENTS_KEY),
        reader.hget(_item_key(1), "checked_at"),
        reader.hget(_item_key(2), "state"),
        BrainIndex(tier, RepoRef(REPO)).watermark(),
    ) == (
        3,
        7,
        rechecked.isoformat(),
        "closed",
        Watermark(changed=NOW - timedelta(hours=1), number=3, synced_at=NOW),
    )


def test_a_sync_copies_at_most_its_bound_and_the_next_one_goes_on_from_the_watermark(
    tier: Any, reader: FakeValkey
) -> None:
    """Three issues changed in the same second and the bound is 2: the sync copies the two with
    the lower numbers, and the next sync copies the third and no issue a second time."""
    issues = [_issue(number, updated_at=NOW) for number in (3, 1, 2)]

    first = sync_brain_index(REPO, issues, tier=tier, limit=2, now=NOW)
    after_first = sorted(reader.scan_iter("roadmap:v1:brain-item:*"))
    second = sync_brain_index(REPO, issues, tier=tier, limit=2, now=NOW)

    assert (first.copied, after_first, second.copied, second.entries, reader.xlen(EVENTS_KEY)) == (
        2,
        [_item_key(1), _item_key(2)],
        1,
        3,
        3,
    )


def test_a_changed_issue_with_no_check_moves_the_watermark_and_writes_no_entry(
    tier: Any, reader: FakeValkey
) -> None:
    """An issue with no check changed, and so did a pull request with the text of a block. The
    sync writes no entry, and its watermark passes the issue, so the next sync does not read it
    again."""
    pull = _issue(9, updated_at=NOW).model_copy(update={"pull_request": True})
    issues = [_issue(5, updated_at=NOW - timedelta(minutes=5), checked_at=None), pull]

    result = sync_brain_index(REPO, issues, tier=tier, now=NOW)

    assert (result, reader.keys("roadmap:v1:brain-item:*")) == (BrainSync(entries=0), [])
    assert BrainIndex(tier, RepoRef(REPO)).watermark() == Watermark(
        changed=NOW - timedelta(minutes=5), number=5, synced_at=NOW
    )


def test_the_entry_of_an_item_names_the_five_nearest_items_of_its_tool(
    tier: Any, reader: FakeValkey
) -> None:
    """Seven items of one repository name one tool. The entry of an item names the 5 other items
    with the newest checks as its near items, and the tool hash names each of the 7."""
    issues = [
        _issue(number, updated_at=NOW, checked_at=CHECKED_AT + timedelta(days=number))
        for number in range(1, 8)
    ]

    sync_brain_index(REPO, issues, tier=tier, now=NOW)

    (tool_key,) = reader.keys("roadmap:v1:brain-tool:*")
    assert (reader.hget(_item_key(1), "near"), reader.hget(tool_key, "items")) == (
        "7 6 5 4 3",
        "1 2 3 4 5 6 7",
    )


# ── The instruments ───────────────────────────────────────────────────────────


def test_a_sync_reports_the_entries_the_lag_and_the_first_reads(
    tier: Any, otlp: FakeCollector
) -> None:
    """The sync writes one item, and the last sync ended 120 s before: `devops_cli_brain_entries`
    reads 1, `devops_cli_brain_sync_lag_seconds{store="brain_index"}` reads 120, and
    `devops_cli_brain_first_reads_total` reads 0, since no check ran in the round."""
    sync_brain_index(REPO, [], tier=tier, now=NOW - timedelta(seconds=120))

    sync_brain_index(REPO, [_issue(1, updated_at=NOW)], tier=tier, now=NOW)

    labels = {"store": "brain_index", "repo": REPO}
    assert (
        _last(otlp, "devops_cli_brain_entries"),
        _last(otlp, "devops_cli_brain_sync_lag_seconds"),
        _summed(otlp, "devops_cli_brain_first_reads_total"),
    ) == ((labels, 1.0), (labels, 120.0), {("alternatives",): 0.0})


# ── A store that is down or not configured ────────────────────────────────────


def test_a_sync_with_no_connection_finishes_counts_one_fallback_and_writes_no_key(
    tier: Any, valkey_server: FakeServer, reader: FakeValkey, otlp: FakeCollector
) -> None:
    """`connected` is False and the snapshot holds 3 changed issues: the sync finishes, counts one
    `fallback` for the store `brain_index`, and the store holds no brain key."""
    issues = [_issue(number, updated_at=NOW) for number in (1, 2, 3)]
    valkey_server.connected = False

    result = sync_brain_index(REPO, issues, tier=tier, now=NOW)

    valkey_server.connected = True
    assert (
        result,
        _summed(otlp, "devops_cli_brain_reads_total"),
        reader.keys("*"),
    ) == (BrainSync(fallback=True), {("fallback", "brain_index"): 1.0}, [])


def test_a_process_with_no_store_counts_one_fallback(otlp: FakeCollector) -> None:
    """A process that names no `roadmap.state.url` has no tier: the sync finishes and counts one
    `fallback`."""
    result = sync_brain_index(REPO, [_issue(1, updated_at=NOW)], tier=None, now=NOW)

    assert (result, _summed(otlp, "devops_cli_brain_reads_total")) == (
        BrainSync(fallback=True),
        {("fallback", "brain_index"): 1.0},
    )


def test_a_store_that_goes_away_in_a_sync_keeps_the_place_of_the_last_copy(
    valkey_server: FakeServer, reader: FakeValkey, otlp: FakeCollector
) -> None:
    """The store answers the copy of the first issue and refuses the copy of the second one with
    a reply error, as a store at its memory bound does. The sync counts one `fallback`, writes no
    sync time, and keeps the place of the first issue, so the next sync goes on with the second
    issue."""
    issues = [_issue(number, updated_at=NOW + timedelta(minutes=number)) for number in (1, 2)]
    writes = FakeValkey(server=valkey_server)
    refusals = [_item_key(2)]

    def refuse_after_the_first_copy(command: tuple[Any, ...]) -> None:
        if command[:1] == ("WATCH",) and command[1] in refusals:
            refusals.remove(command[1])
            writes.set(command[1], "not a hash")

    client = valkey_client_on(valkey_server, after_command=refuse_after_the_first_copy)
    tier = _tier(client)
    try:
        refused = sync_brain_index(REPO, issues, tier=tier, now=NOW)
        watermark = BrainIndex(tier, RepoRef(REPO)).watermark()
        writes.delete(_item_key(2))
        resumed = sync_brain_index(REPO, issues, tier=tier, now=NOW + timedelta(hours=1))
    finally:
        client.close()

    assert (refused, watermark, resumed, reader.xlen(EVENTS_KEY)) == (
        BrainSync(copied=1, fallback=True),
        Watermark(changed=NOW + timedelta(minutes=1), number=1),
        BrainSync(copied=1, entries=2),
        2,
    )
    assert _summed(otlp, "devops_cli_brain_reads_total") == {("fallback", "brain_index"): 1.0}


# ── The round of the alternatives check ───────────────────────────────────────

Config = Callable[..., Any]


@pytest.fixture
def searches(config: Config, monkeypatch: pytest.MonkeyPatch, web: WebFake) -> None:
    """A Firecrawl key in the settings, and a Firecrawl that answers each search with one result:
    the check of a public repository is on."""
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config(search={"providers": ["firecrawl"]}, firecrawl={"api_key": "fc-test"})
    results = [{"title": "Result", "url": "https://example.com/widgets", "description": "Text."}]
    web.content(
        DEFAULT_FIRECRAWL_SEARCH_URL,
        json.dumps({"success": True, "data": {"web": results}}).encode(),
    )


def _roadmap(*titles: str, is_private: bool = False) -> InMemoryRoadmapStore:
    """A roadmap with one open New item for each title."""
    store = InMemoryRoadmapStore(repo=REPO, is_private=is_private)
    for title in titles:
        store.seed_issue(
            title,
            body="The item needs widgets.",
            fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"},
        )
    return store


def _no_tool_found(messages: list[ModelMessage]) -> Any:
    """A model that searches one time and then says that no tool covers the item."""
    searched = any(
        isinstance(part, ToolReturnPart) and part.tool_name == "search_web"
        for message in messages
        for part in getattr(message, "parts", ())
    )
    if searched:
        return AlternativesReply(reason="No open tool covers the need.", verdict=Verdict.NONE)
    return call("search_web", query="widgets")


@pytest.mark.usefixtures("searches")
def test_the_check_of_an_item_with_no_entry_writes_its_verdict_to_the_block_and_the_index(
    roadmap_state_valkey: ValkeyCacheTier, reader: FakeValkey, otlp: FakeCollector
) -> None:
    """The index holds no entry for the item, and the check finds the verdict `none`: the round
    writes `none` to the block and to the index, and `devops_cli_brain_first_reads_total` counts
    1."""
    store = _roadmap("Build a widget")
    model = Script(_no_tool_found).model()

    plan = plan_alternatives(
        store, repo=REPO, investigator=model, writer=AlternativesWriter(store, REPO), now=NOW
    )
    result = sync_alternatives_round(store, plan, now=NOW)

    assert (
        f"Alternatives check of {NOW.date().isoformat()}: none." in store.read_issue_body(1),
        reader.hmget(_item_key(1), "verdict", "checked_at", "tool_id"),
        result,
        _summed(otlp, "devops_cli_brain_first_reads_total"),
    ) == (
        True,
        ["none", NOW.isoformat(), ""],
        BrainSync(copied=1, first_reads=1, entries=1),
        {("alternatives",): 1.0},
    )


@pytest.mark.usefixtures("searches")
def test_a_round_with_no_connection_finishes_and_counts_one_fallback(
    roadmap_state_valkey: ValkeyCacheTier,
    valkey_server: FakeServer,
    reader: FakeValkey,
    otlp: FakeCollector,
) -> None:
    """The store is down while a round checks 3 items of a skip class: the round writes its 3
    blocks, finishes, counts one `fallback` and writes no brain key."""
    store = _roadmap(
        "docs: describe widget 1", "docs: describe widget 2", "docs: describe widget 3"
    )
    valkey_server.connected = False

    plan = plan_alternatives(store, repo=REPO, writer=AlternativesWriter(store, REPO), now=NOW)
    result = sync_alternatives_round(store, plan, now=NOW)

    valkey_server.connected = True
    blocks = ["Alternatives check of" in store.read_issue_body(number) for number in (1, 2, 3)]
    assert (blocks, result, _summed(otlp, "devops_cli_brain_reads_total"), reader.keys("*")) == (
        [True, True, True],
        BrainSync(fallback=True),
        {("fallback", "brain_index"): 1.0},
        [],
    )


def test_a_round_whose_check_is_off_makes_no_sync(
    roadmap_state_valkey: ValkeyCacheTier, reader: FakeValkey, otlp: FakeCollector
) -> None:
    """The check is off for a private repository, so the round reads no listing: the step makes no
    sync, counts nothing and writes no key, and no entry of a private repository exists."""
    store = _roadmap("Build a widget", is_private=True)

    plan = plan_alternatives(store, repo=REPO, writer=AlternativesWriter(store, REPO), now=NOW)
    result = sync_alternatives_round(store, plan, now=NOW)

    assert (
        plan.off_reason is not None,
        result,
        otlp.points("devops_cli_brain_reads_total"),
        reader.keys("*"),
    ) == (True, None, [], [])
