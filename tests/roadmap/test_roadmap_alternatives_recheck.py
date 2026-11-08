"""A recheck of an item posts a comment only when its result changed (#4054).

An item is checked again after `recheck_days`. A check always writes its block and its marks, so
the date moves and the item is not due before the days pass again. The comment is the only write
that depends on the result: it is posted for a first check, and for a recheck whose verdict or tool
differs from the recorded `alternatives.verdict` and `alternatives.tool`.

The roadmap is the in-memory store. A check comes from `validate_reply`, so no test reaches a
model, a search or the web.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from devops_cli.config.constants import CONST_ROADMAP_ALTERNATIVES_START_MARKER
from devops_cli.roadmap import alternatives
from devops_cli.roadmap.alternatives import (
    AlternativesReply,
    AlternativesTools,
    AlternativesWriter,
    Check,
    ToolFacts,
    Verdict,
    select_items,
)
from devops_cli.roadmap.stores.store import AlternativesRecordKey, ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
FIRST = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
RECHECK_DAYS = 30
SECOND = FIRST + timedelta(days=RECHECK_DAYS + 1)
TOOL_A = "https://github.com/example/scanner-a"
TOOL_B = "https://github.com/example/scanner-b"
NO_TOOL = None


def _item_number(store: InMemoryRoadmapStore) -> int:
    """An open New item that a check takes."""
    return store.seed_issue(
        "Scan a directory",
        body="The job needs to read every file of a directory.",
        fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"},
        author_association="COLLABORATOR",
    )


def _check(
    store: InMemoryRoadmapStore,
    number: int,
    now: datetime,
    verdict: Verdict,
    tool_url: str | None,
) -> Check:
    """The check of item `number` at `now` that says `verdict`, with the tool at `tool_url`. The
    item is read again, so it holds the marks of the earlier check."""
    item = store.item(number)
    assert item is not None
    tools = AlternativesTools(store=store)
    tools.searches.append(alternatives.Search("scanner", 1))
    if tool_url is not None:
        name = tool_url.rsplit("/", 1)[-1]
        tools.facts[tool_url] = ToolFacts(
            name=name, url=tool_url, license="MIT", last_activity=now - timedelta(days=3)
        )
    reply = AlternativesReply(
        reason="A recheck gives a reason.", verdict=verdict, tool_url=tool_url
    )
    check = alternatives.validate_reply(item, reply, tools, now, ())
    assert isinstance(check, Check)
    return check


def _comments(store: InMemoryRoadmapStore, number: int) -> int:
    """How many comments the item holds."""
    return len(store.comments_on(number))


def _first_check(
    store: InMemoryRoadmapStore, number: int, verdict: Verdict, tool_url: str | None
) -> None:
    """Write the first check of the item at `FIRST`."""
    AlternativesWriter(store).settle(_check(store, number, FIRST, verdict, tool_url))


def _due_numbers(store: InMemoryRoadmapStore, now: datetime) -> list[int]:
    """The numbers of the items that the next round takes at `now`."""
    selection = select_items(
        store, item_number=None, limit=5, recheck_days=RECHECK_DAYS, retry_days=3, now=now
    )
    return [item.number for item in selection.selected]


def test_first_check_posts_its_comment() -> None:
    """An item with no recorded verdict has never been checked, so its check posts a comment."""
    store = InMemoryRoadmapStore(repo=REPO)
    number = _item_number(store)

    AlternativesWriter(store).settle(_check(store, number, FIRST, Verdict.NONE, NO_TOOL))
    item = store.item(number)
    assert item is not None

    assert (
        _comments(store, number),
        item.job_record.get(AlternativesRecordKey.VERDICT),
        item.job_record.get(AlternativesRecordKey.CHECKED_AT),
    ) == (1, "none", FIRST.isoformat())


@pytest.mark.parametrize(
    ("verdict", "tool_url"),
    [(Verdict.NONE, NO_TOOL), (Verdict.COVERS, TOOL_A)],
    ids=["no_tool", "same_tool"],
)
def test_same_verdict_and_tool_posts_no_second_comment_and_moves_the_date(
    verdict: Verdict, tool_url: str | None
) -> None:
    """A recheck with the verdict and the tool of the record posts no comment. It writes the block
    and the marks, so the date moves and the item is not due again before the days pass."""
    store = InMemoryRoadmapStore(repo=REPO)
    number = _item_number(store)
    _first_check(store, number, verdict, tool_url)
    assert _due_numbers(store, SECOND) == [number]

    AlternativesWriter(store).settle(_check(store, number, SECOND, verdict, tool_url))
    item = store.item(number)
    assert item is not None

    assert (
        _comments(store, number),
        item.job_record.get(AlternativesRecordKey.CHECKED_AT),
        item.job_record.get(AlternativesRecordKey.VERDICT),
        item.job_record.get(AlternativesRecordKey.TOOL),
        CONST_ROADMAP_ALTERNATIVES_START_MARKER in item.body,
        SECOND.date().isoformat() in item.body,
        _due_numbers(store, SECOND),
    ) == (
        1,
        SECOND.isoformat(),
        verdict.value,
        tool_url,
        True,
        True,
        [],
    )


def test_same_verdict_and_tool_makes_one_write_and_no_comment_request() -> None:
    """The write of a recheck with the same result is the one write of the issue. The comment
    request is not made (#4049 keeps the one write)."""
    store = InMemoryRoadmapStore(repo=REPO)
    number = _item_number(store)
    _first_check(store, number, Verdict.NONE, NO_TOOL)
    before = len(store.writes)

    AlternativesWriter(store).settle(_check(store, number, SECOND, Verdict.NONE, NO_TOOL))

    assert store.writes[before:] == ["set_marks"]


def test_same_verdict_and_tool_still_counts_the_check() -> None:
    """The writer counts a recheck that posts no comment: the count is the count of checks written,
    and a comment is not what it counts."""
    store = InMemoryRoadmapStore(repo=REPO)
    number = _item_number(store)
    _first_check(store, number, Verdict.NONE, NO_TOOL)
    writer = AlternativesWriter(store)

    writer.settle(_check(store, number, SECOND, Verdict.NONE, NO_TOOL))

    assert writer.written == 1


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ((Verdict.NONE, NO_TOOL), (Verdict.COVERS, TOOL_A)),
        ((Verdict.COVERS, TOOL_A), (Verdict.NONE, NO_TOOL)),
        ((Verdict.COVERS, TOOL_A), (Verdict.PARTLY, TOOL_A)),
    ],
    ids=["none_to_covers", "covers_to_none", "covers_to_partly_same_tool"],
)
def test_changed_verdict_posts_one_comment(
    first: tuple[Verdict, str | None], second: tuple[Verdict, str | None]
) -> None:
    """A recheck whose verdict differs from the record posts one more comment, and it records the
    new verdict and the new date."""
    store = InMemoryRoadmapStore(repo=REPO)
    number = _item_number(store)
    _first_check(store, number, *first)

    AlternativesWriter(store).settle(_check(store, number, SECOND, *second))
    item = store.item(number)
    assert item is not None

    assert (
        _comments(store, number),
        item.job_record.get(AlternativesRecordKey.VERDICT),
        item.job_record.get(AlternativesRecordKey.CHECKED_AT),
    ) == (2, second[0].value, SECOND.isoformat())


def test_changed_tool_with_the_same_verdict_posts_one_comment() -> None:
    """A recheck that gives the same verdict with another tool posts one more comment."""
    store = InMemoryRoadmapStore(repo=REPO)
    number = _item_number(store)
    _first_check(store, number, Verdict.COVERS, TOOL_A)

    AlternativesWriter(store).settle(_check(store, number, SECOND, Verdict.COVERS, TOOL_B))
    item = store.item(number)
    assert item is not None

    assert (
        _comments(store, number),
        item.job_record.get(AlternativesRecordKey.TOOL),
    ) == (2, TOOL_B)


def test_changed_result_makes_the_write_then_the_comment() -> None:
    """The requests of a recheck with a new result are the one write and then the comment."""
    store = InMemoryRoadmapStore(repo=REPO)
    number = _item_number(store)
    _first_check(store, number, Verdict.NONE, NO_TOOL)
    before = len(store.writes)

    AlternativesWriter(store).settle(_check(store, number, SECOND, Verdict.COVERS, TOOL_A))

    assert store.writes[before:] == ["set_marks", "comment"]
