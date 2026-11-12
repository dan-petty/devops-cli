"""An alternatives check writes its block and its marks with one request (#4049).

The new body, with the job's block, and `checked_at` go in one `PATCH`. A stop of the Service
after that write leaves the block and `checked_at` together, so the next round does not take the
item as one with no check. The comment is a separate request after the write.

The roadmap is the in-memory store. The check comes from `validate_reply`, so no test reaches a
model, a search or the web.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from devops_cli.config.constants import CONST_ROADMAP_ALTERNATIVES_START_MARKER
from devops_cli.exceptions import RoadmapRunError
from devops_cli.roadmap import alternatives
from devops_cli.roadmap.alternatives import (
    AlternativesReply,
    AlternativesTools,
    AlternativesWriter,
    Check,
    Verdict,
    select_items,
)
from devops_cli.roadmap.stores.store import AlternativesRecordKey, ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.service_stop import stop_error

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


def _checked_item(store: InMemoryRoadmapStore) -> tuple[int, Check]:
    """An open New item, and the check of it that says no tool covers the need."""
    number = store.seed_issue(
        "Scan a directory",
        body="The job needs to read every file of a directory.",
        fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"},
        author_association="COLLABORATOR",
    )
    item = store.item(number)
    assert item is not None
    tools = AlternativesTools(store=store)
    tools.searches.append(alternatives.Search("scanner", 1))
    reply = AlternativesReply(reason="Nothing fits the need.", verdict=Verdict.NONE)
    check = alternatives.validate_reply(item, reply, tools, NOW, ())
    assert isinstance(check, Check)
    return number, check


def _selected(store: InMemoryRoadmapStore) -> list[int]:
    """The numbers of the items the next round takes."""
    selection = select_items(
        store, item_number=None, limit=5, recheck_days=30, retry_days=3, now=NOW
    )
    return [item.number for item in selection.selected]


def test_a_stop_after_write_leaves_the_block_and_checked_at_together() -> None:
    """The only write of a check is one request. A stop right after it leaves the new block and
    `checked_at` together, so the next round does not take the item again (#4049)."""
    store = InMemoryRoadmapStore(repo=REPO)
    number, check = _checked_item(store)
    store.fail_write(at=2, error=stop_error())

    with pytest.raises(RoadmapRunError) as stopped:
        AlternativesWriter(store, REPO).settle(check)
    item = store.item(number)
    assert item is not None

    assert (
        stopped.value.error_code,
        CONST_ROADMAP_ALTERNATIVES_START_MARKER in item.body,
        item.job_record.get(AlternativesRecordKey.CHECKED_AT),
        item.job_record.get(AlternativesRecordKey.VERDICT),
        _selected(store),
    ) == ("SERVICE_STOPPING", True, NOW.isoformat(), "none", [])


def test_a_check_is_one_write_that_holds_the_block_and_the_marks_then_the_comment() -> None:
    """A check costs one write of its issue and one comment. The write changes no label (#4049)."""
    store = InMemoryRoadmapStore(repo=REPO)
    number, check = _checked_item(store)
    labels = store.issues()[0].labels
    before = len(store.writes)

    AlternativesWriter(store, REPO).settle(check)
    item = store.item(number)
    assert item is not None

    assert (
        store.writes[before:],
        store.issues()[0].labels,
        CONST_ROADMAP_ALTERNATIVES_START_MARKER in item.body,
        item.job_record.get(AlternativesRecordKey.CHECKED_AT),
    ) == (["set_marks", "comment"], labels, True, NOW.isoformat())
