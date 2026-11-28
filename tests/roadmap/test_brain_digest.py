"""The brain digest that the alternatives check reads before its model call (#4682, ADR 0023
section 1).

The digest holds the near items of the entry of the item in the brain index, each with the date of
its check, its verdict, the canonical id and the name of its tool, and the ADRs in force that
reject that tool. It holds whole entries and at most 2,000 tokens. The request of the model holds it
under the key `brain`, and a written check records the entries that it used in
`alternatives.brain_used`. A brain that is off, not configured, down or not built gives an empty
digest, and the check runs as before.

The store is the in-memory Valkey, which the real `BrainIndex` writes. The roadmap of a run is the
in-memory store, pydantic-ai's `FunctionModel` answers the model request of a check, and Firecrawl
is answered at the HTTP edge.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fakeredis import FakeServer, FakeValkey
from pydantic_ai.messages import ModelMessage, ToolReturnPart

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_URL
from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.adr import Adr, adr_of
from devops_cli.roadmap.alternatives import AlternativesReply, AlternativesWriter, plan_alternatives
from devops_cli.roadmap.brain_digest import read_digest
from devops_cli.roadmap.brain_entries import BrainEntry, tool_key_id
from devops_cli.roadmap.brain_index import BrainIndex, Related
from devops_cli.roadmap.stores.store import AlternativesRecordKey, GitHubState, ItemField, Verdict
from tests.support.fakes.http import WebFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.fakes.valkey import valkey_client_on
from tests.support.scripted_model import Script, call

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "acme/widgets"
NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
FIRST = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
TOOL_ID = "github.com/acme/widget-kit"
TOOL_NAME = "Widget Kit"
MAX_TOKENS = 2000

Config = Callable[..., Path]


def _tier(client: Any) -> Any:
    """The tier of the roadmap state over `client`."""
    from devops_cli.valkey.cache import ValkeyCacheTier

    return ValkeyCacheTier(client)


@pytest.fixture
def index(valkey_server: FakeServer) -> Iterator[BrainIndex]:
    """The brain index of `REPO` over the in-memory Valkey, which writes the fixture brain."""
    client = valkey_client_on(valkey_server)
    yield BrainIndex(_tier(client), RepoRef(REPO))
    client.close()


def _entry(
    number: int,
    *,
    checked_at: datetime = FIRST,
    verdict: Verdict = Verdict.PARTLY,
    tool_id: str = TOOL_ID,
    tool_name: str = TOOL_NAME,
) -> BrainEntry:
    """The entry of the check of item `number`, of a tool unless `tool_id` is empty."""
    return BrainEntry(
        number=number,
        state=GitHubState.OPEN,
        verdict=verdict,
        checked_at=checked_at,
        body_hash=f"{number:064x}",
        adr_hash="a" * 64,
        tool_id=tool_id,
        tool_url=f"https://{tool_id}" if tool_id else "",
        tool_name=tool_name if tool_id else "",
        refs=(),
        uses=(),
    )


def _brain(index: BrainIndex, number: int, near: Sequence[BrainEntry]) -> None:
    """Write the entry of each of `near`, then the entry of item `number` with `near` as its near
    items, in their order."""
    for entry in near:
        index.write(entry, Related())
    index.write(_entry(number), Related(near=tuple(entry.number for entry in near)))


def _value(entry: BrainEntry, *, rejected_by: Sequence[str] = ()) -> dict[str, Any]:
    """The digest entry of `entry` as the request of the model holds it."""
    tool = (
        {"tool": entry.tool_id, "tool_name": entry.tool_name, "rejected_by": list(rejected_by)}
        if entry.tool_id
        else {}
    )
    return {
        "item": entry.number,
        "checked": entry.checked_at.date().isoformat(),
        "verdict": entry.verdict.value,
        **tool,
    }


def _adr(number: int, title: str, options: str) -> Adr:
    """The ADR `number` in force with `title` and the `options` of its `Considered Options`."""
    adr = adr_of(
        f"docs/adr/{number:04d}-decision.md",
        f"# {title}\n\nThe text.\n\n## Considered Options\n\n{options}\n",
    )
    assert adr is not None
    return adr


# ── The digest of the brain index ─────────────────────────────────────────────


def test_the_digest_holds_the_five_near_items_with_their_verdicts_and_tools(
    index: BrainIndex,
) -> None:
    """The entry of item 1 names 5 near items, each with a verdict and a canonical tool id. The
    digest holds the 5 items in the order of the entry, newest check first, each with its date,
    its verdict and its tool."""
    near = [
        _entry(number, checked_at=FIRST + timedelta(days=7 - number), verdict=verdict)
        for number, verdict in zip(
            range(2, 7),
            (Verdict.COVERS, Verdict.PARTLY, Verdict.IN_USE, Verdict.PARTLY, Verdict.COVERS),
            strict=True,
        )
    ]
    _brain(index, 1, near)

    digest = read_digest(index, 1, ())

    assert digest.value() == [_value(entry) for entry in near]


def test_the_digest_holds_the_date_of_the_check_of_each_near_item(index: BrainIndex) -> None:
    """The brain holds the verdict `partly` of item 2 with the check time 2026-11-01 09:30 UTC:
    the digest holds the verdict with the date 2026-11-01."""
    _brain(index, 1, [_entry(2, checked_at=FIRST, verdict=Verdict.PARTLY)])

    digest = read_digest(index, 1, ())

    assert [(entry["checked"], entry["verdict"]) for entry in digest.value()] == [
        ("2026-11-01", "partly")
    ]


def test_a_digest_over_2000_tokens_leaves_out_each_whole_entry_that_does_not_fit(
    index: BrainIndex,
) -> None:
    """The tool names of 5 near items hold about 900, 1,200, 300, 1,200 and 10 tokens, about
    3,600 together. The digest holds the first entry, leaves out the second, which does not fit
    after it, and holds the third and the fifth, which fit after the first."""
    sizes = (900, 1200, 300, 1200, 10)
    near = [
        _entry(number, tool_id=f"github.com/acme/kit-{number}", tool_name="kit " * size)
        for number, size in zip(range(2, 7), sizes, strict=True)
    ]
    _brain(index, 1, near)

    digest = read_digest(index, 1, ())

    assert digest.value() == [_value(near[0]), _value(near[2]), _value(near[4])]


def test_the_digest_names_the_adr_in_force_that_rejects_the_tool_of_a_near_item(
    index: BrainIndex,
) -> None:
    """ADR 0008 rejects Temporal under a rejected option and chooses Argo Workflows. The near item
    of Temporal holds ADR 0008, and the near item of Argo Workflows holds no ADR."""
    temporal = _entry(2, tool_id="github.com/temporalio/temporal", tool_name="Temporal")
    argo = _entry(3, tool_id="github.com/argoproj/argo-workflows", tool_name="Argo Workflows")
    _brain(index, 1, [temporal, argo])
    adrs = (
        _adr(
            8,
            "Durable runs",
            "- **Temporal**: rejected. It needs a server of its own.\n"
            "- **Argo Workflows**: chosen.",
        ),
    )

    digest = read_digest(index, 1, adrs)

    assert digest.value() == [_value(temporal, rejected_by=["ADR 0008"]), _value(argo)]


def test_the_near_items_leave_out_the_item_itself_and_a_repeated_number(
    index: BrainIndex, valkey_server: FakeServer
) -> None:
    """The `near` field of the entry of item 1 is `1 1 2 2`: the digest holds item 2 one time."""
    _brain(index, 1, [_entry(2)])
    FakeValkey(server=valkey_server).hset("roadmap:v1:brain-item:acme/widgets:1", "near", "1 1 2 2")

    digest = read_digest(index, 1, ())

    assert (digest.value(), digest.used) == (
        [_value(_entry(2))],
        ("item:1", "item:2", f"tool:{tool_key_id(TOOL_ID)}"),
    )


def test_a_near_item_with_no_entry_or_an_entry_of_another_form_gives_no_digest_entry(
    index: BrainIndex, valkey_server: FakeServer
) -> None:
    """The entry of item 1 names items 2, 3, 4 and 5. The index holds no entry of item 3, the
    entry of item 4 is of another schema, and the tool entry of item 5 has expired. The digest
    holds item 2 and item 5, the second with no tool name."""
    near = [_entry(2), _entry(3), _entry(4), _entry(5, tool_id="github.com/acme/frames")]
    _brain(index, 1, near)
    writer = FakeValkey(server=valkey_server, decode_responses=True)
    writer.delete("roadmap:v1:brain-item:acme/widgets:3")
    writer.hset("roadmap:v1:brain-item:acme/widgets:4", "schema", "0")
    writer.delete(f"roadmap:v1:brain-tool:acme/widgets:{tool_key_id('github.com/acme/frames')}")

    digest = read_digest(index, 1, ())

    without_name = _value(near[3])
    del without_name["tool_name"]
    assert (digest.value(), digest.used) == (
        [_value(near[0]), without_name],
        ("item:1", "item:2", f"tool:{tool_key_id(TOOL_ID)}", "item:5"),
    )


def test_an_item_with_no_entry_and_an_entry_with_no_near_item_give_an_empty_digest(
    index: BrainIndex,
) -> None:
    """The index holds no entry of item 7, and the entry of item 1 names no near item: both
    digests are empty and name no used entry."""
    _brain(index, 1, [])

    digests = [read_digest(index, number, ()) for number in (7, 1)]

    assert [(digest.value(), digest.used) for digest in digests] == [([], ()), ([], ())]


def test_a_digest_with_no_index_is_empty() -> None:
    """A run with no brain index, as on a workstation, reads an empty digest."""
    digest = read_digest(None, 1, ())

    assert (digest.value(), digest.used) == ([], ())


# ── The digest in the check ───────────────────────────────────────────────────


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


def _roadmap(*titles: str) -> InMemoryRoadmapStore:
    """A public roadmap with one open New item for each title, items 1, 2 and so on."""
    store = InMemoryRoadmapStore(repo=REPO, is_private=False)
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


def _check(store: InMemoryRoadmapStore) -> Script:
    """Check the items of `store` in one written round, and give the script of the model."""
    script = Script(_no_tool_found)
    plan_alternatives(
        store,
        repo=REPO,
        investigator=script.model(),
        writer=AlternativesWriter(store, REPO),
        now=NOW,
    )
    return script


def _request(script: Script, index: int = 0) -> dict[str, Any]:
    """The request of the model at `index`, as the model read it."""
    request: dict[str, Any] = json.loads(script.prompt(index))
    return request


def _brain_text(script: Script) -> str | None:
    """The text of the value of `brain` in the first request of the model, as the model read it;
    None when the request holds no `brain`."""
    text = script.prompt(0)
    start = text.find('"brain": ')
    if start < 0:
        return None
    return text[start + len('"brain": ') : text.index(',\n "search_budget"')]


# The JSON fields of a digest entry with a tool.
ENTRY_KEYS = ["checked", "item", "rejected_by", "tool", "tool_name", "verdict"]


@pytest.mark.usefixtures("searches", "roadmap_state_valkey")
def test_the_area_read_is_empty_while_the_index_holds_no_area_check(index: BrainIndex) -> None:
    """The brain index of #4676 has no kind of entry for an area check. The request of an item
    with 2 near items holds no `area`, and each entry of its digest holds no `area`."""
    _brain(index, 1, [_entry(2), _entry(3, verdict=Verdict.COVERS)])

    request = _request(_check(_roadmap("Build a widget")))

    assert ("area" in request, [sorted(entry) for entry in request["brain"]]) == (
        False,
        [ENTRY_KEYS, ENTRY_KEYS],
    )


@pytest.mark.usefixtures("searches", "roadmap_state_valkey")
@pytest.mark.parametrize(
    ("words", "held"),
    [pytest.param(1938, True, id="2000-tokens-as-sent"), pytest.param(1940, False, id="2002")],
)
def test_the_digest_as_the_request_holds_it_has_at_most_2000_tokens(
    index: BrainIndex, words: int, held: bool
) -> None:
    """The tool name of the one near item of item 1 holds `words` words. As the request holds
    it, one level down in the JSON of the request, the digest of 1,938 words holds 2,000 tokens
    and stays. The digest of 1,940 words holds 2,002 tokens there, so the request holds no
    `brain`. As a JSON document of its own, that digest holds 2,000 tokens."""
    _brain(index, 1, [_entry(2, tool_id="github.com/acme/kit-2", tool_name="kit " * words)])

    text = _brain_text(_check(_roadmap("Build a widget")))

    assert (text is not None, text is None or count_tokens(text) <= MAX_TOKENS) == (held, True)


def _corrupt_near(server: FakeServer) -> None:
    """The `near` field of the entry of item 1 holds a word of 5,000 digits between 2 and 3."""
    near = f"2 {'9' * 5000} 3"
    FakeValkey(server=server).hset("roadmap:v1:brain-item:acme/widgets:1", "near", near)


def _name_on_own_entry(server: FakeServer) -> None:
    """The hash of the entry of item 1 holds a field whose name is not UTF-8."""
    FakeValkey(server=server).hset("roadmap:v1:brain-item:acme/widgets:1", b"\xff\xfe", b"x")


def _name_on_near_entry(server: FakeServer) -> None:
    """The hash of the entry of near item 2 holds a field whose name is not UTF-8."""
    FakeValkey(server=server).hset("roadmap:v1:brain-item:acme/widgets:2", b"\xff\xfe", b"x")


@pytest.mark.usefixtures("searches", "roadmap_state_valkey")
@pytest.mark.parametrize(
    "corrupt",
    [
        pytest.param(_corrupt_near, id="near-word-of-5000-digits"),
        pytest.param(_name_on_own_entry, id="non-utf8-field-name-on-the-entry-of-the-item"),
        pytest.param(_name_on_near_entry, id="non-utf8-field-name-on-a-near-entry"),
    ],
)
def test_a_brain_entry_of_a_wrong_form_leaves_the_round_and_its_verdict_whole(
    index: BrainIndex, valkey_server: FakeServer, corrupt: Callable[[FakeServer], None]
) -> None:
    """The brain holds near items 2 and 3 of item 1, and then one of its hashes gets a value or a
    field name of a wrong form. The round completes, the check writes the verdict of its reply,
    and the digest holds the 2 sound near items."""
    near = [_entry(2), _entry(3)]
    _brain(index, 1, near)
    corrupt(valkey_server)
    store = _roadmap("Build a widget")

    script = _check(store)

    item = store.item(1)
    assert item is not None
    assert (
        item.job_record.get(AlternativesRecordKey.VERDICT),
        _request(script).get("brain"),
    ) == ("none", [_value(entry) for entry in near])


@pytest.mark.usefixtures("searches", "roadmap_state_valkey")
def test_the_request_holds_the_brain_key_for_a_digest_and_none_for_an_empty_digest(
    index: BrainIndex,
) -> None:
    """The entry of item 1 names 2 near items, and the index holds no entry of item 2. The request
    of item 1 holds `brain` with the 2 entries, and the request of item 2 holds no `brain`."""
    near = [_entry(10), _entry(11, verdict=Verdict.COVERS)]
    _brain(index, 1, near)
    store = _roadmap("Build a widget", "Build a frame")

    script = _check(store)

    assert (_request(script, 0).get("brain"), "brain" in _request(script, 2)) == (
        [_value(entry) for entry in near],
        False,
    )


@pytest.mark.usefixtures("searches", "roadmap_state_valkey")
def test_a_check_with_a_digest_makes_as_many_model_calls_as_a_check_with_an_empty_digest(
    index: BrainIndex, valkey_server: FakeServer
) -> None:
    """Item 1 is checked with a digest of 5 near items, and then the same item is checked with an
    empty digest: each check makes 2 model calls, a search and the reply."""
    _brain(index, 1, [_entry(number) for number in range(2, 7)])
    with_digest = _check(_roadmap("Build a widget"))
    FakeValkey(server=valkey_server).flushall()
    empty = _check(_roadmap("Build a widget"))

    assert (
        len(with_digest.seen),
        len(empty.seen),
        len(_request(with_digest).get("brain", [])),
        "brain" in _request(empty),
    ) == (2, 2, 5, False)


def _store_down(request: pytest.FixtureRequest, index: BrainIndex) -> None:
    """The brain holds 2 near items of item 1, and the store answers no command."""
    request.getfixturevalue("roadmap_state_valkey")
    _brain(index, 1, [_entry(2), _entry(3)])
    request.getfixturevalue("valkey_server").connected = False


def _no_store(request: pytest.FixtureRequest, index: BrainIndex) -> None:
    """The brain holds 2 near items of item 1, and the settings name no `roadmap.state.url`, as on
    a workstation."""
    _brain(index, 1, [_entry(2), _entry(3)])


def _not_built(request: pytest.FixtureRequest, index: BrainIndex) -> None:
    """The store answers, and the brain index holds no entry."""
    request.getfixturevalue("roadmap_state_valkey")


@pytest.mark.usefixtures("searches")
@pytest.mark.parametrize(
    "brain",
    [
        pytest.param(_store_down, id="valkey-down"),
        pytest.param(_no_store, id="no-roadmap-state-url"),
        pytest.param(_not_built, id="index-not-built"),
    ],
)
def test_a_brain_that_is_not_available_gives_no_brain_key_and_the_check_of_today(
    request: pytest.FixtureRequest,
    index: BrainIndex,
    brain: Callable[[pytest.FixtureRequest, BrainIndex], None],
) -> None:
    """The request holds no `brain`, and the check writes the verdict of the reply, `none`, with
    no used entry."""
    brain(request, index)
    store = _roadmap("Build a widget")

    script = _check(store)

    item = store.item(1)
    assert item is not None
    assert (
        "brain" in _request(script),
        f"Alternatives check of {NOW.date().isoformat()}: none." in item.body,
        item.job_record.get(AlternativesRecordKey.VERDICT),
        AlternativesRecordKey.BRAIN_USED in item.job_record,
    ) == (False, True, "none", False)


@pytest.mark.usefixtures("searches")
def test_the_digest_switch_off_makes_no_brain_read(
    config: Config, index: BrainIndex, valkey_server: FakeServer
) -> None:
    """With `roadmap.brain.digest` unset, the check reads the brain and its request holds `brain`.
    With `off`, the next check sends no command to the store and its request holds no `brain`."""
    from devops_cli.valkey.cache import install_roadmap_state_tier

    _brain(index, 1, [_entry(2), _entry(3)])
    sent: list[tuple[Any, ...]] = []
    client = valkey_client_on(valkey_server, after_command=sent.append)
    install_roadmap_state_tier(_tier(client))
    try:
        default = _check(_roadmap("Build a widget"))
        read_by_default = bool(sent)
        sent.clear()
        config(roadmap={"brain": {"digest": "off"}})
        off = _check(_roadmap("Build a widget"))
    finally:
        client.close()

    assert (read_by_default, "brain" in _request(default), sent, "brain" in _request(off)) == (
        True,
        True,
        [],
        False,
    )


@pytest.mark.usefixtures("searches", "roadmap_state_valkey")
def test_a_digest_of_eleven_entries_records_ten_used_entries_in_one_write(
    index: BrainIndex,
) -> None:
    """The digest of item 1 takes 11 brain entries: the entry of item 1, and 5 near items that
    each name a tool of their own. `alternatives.brain_used` holds the first 10 entry ids, and the
    check writes the block and the marks in one write of the issue."""
    near = [_entry(number, tool_id=f"github.com/acme/kit-{number}") for number in range(2, 7)]
    _brain(index, 1, near)
    store = _roadmap("Build a widget")
    before = len(store.writes)

    _check(store)

    item = store.item(1)
    assert item is not None
    used = ["item:1"]
    for entry in near:
        used += [f"item:{entry.number}", f"tool:{tool_key_id(entry.tool_id)}"]
    assert (
        item.job_record.get(AlternativesRecordKey.BRAIN_USED),
        store.writes[before:],
    ) == (" ".join(used[:10]), ["set_marks", "comment"])


@pytest.mark.usefixtures("searches", "roadmap_state_valkey")
def test_a_check_with_an_empty_digest_clears_the_used_entries_of_an_earlier_check() -> None:
    """The record of item 1 holds `alternatives.brain_used` of an earlier check, and the index holds
    no entry of the item: the check clears the key to null."""
    store = _roadmap("Build a widget")
    earlier = store.item(1)
    assert earlier is not None
    store.set_marks(earlier, {AlternativesRecordKey.BRAIN_USED: "item:1 item:9"})

    _check(store)

    item = store.item(1)
    assert item is not None
    assert (
        item.job_record.get(AlternativesRecordKey.VERDICT),
        AlternativesRecordKey.BRAIN_USED in item.job_record,
        item.job_record.get(AlternativesRecordKey.BRAIN_USED),
    ) == ("none", True, None)
