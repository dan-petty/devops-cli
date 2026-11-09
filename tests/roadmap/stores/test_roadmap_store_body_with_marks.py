"""The writes of an item that carry a new body: `set_marks` and `set_field` take an optional
`body` and send it with the labels and the record block in one `PATCH` of the issue (#4049).

A job writes the result of one item with one request, so a stop between two requests cannot leave
the new body with the old marks.
"""

from __future__ import annotations

import json

import pytest

from devops_cli.roadmap.stores.github_store import issue_edit_args
from devops_cli.roadmap.stores.store import ItemField, RefineRecordKey, RoadmapStore
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_github_store import REPO, read, seeded

RECORD = "<!-- devops-roadmap-record"


def test_set_marks_body_sends_one_patch_with_the_new_body_and_the_record_block() -> None:
    """The issue is read once, then one `PATCH` carries the new body and the block that holds the
    marks. It carries no labels (#4049)."""
    github, store = seeded(i7=("priority/p2-medium",))
    item = read(store, 7)
    sent = len(github.calls)

    store.set_marks(item, {RefineRecordKey.BODY_HASH: "b1"}, body="New text")

    block = f'{RECORD} {{"refine.body_hash": "b1"}} -->'
    assert (
        github.calls[sent:],
        json.loads(github.stdins[-1] or "{}"),
        github.body(7),
        github.labels(7),
        read(store, 7).job_record,
    ) == (
        [["api", f"repos/{REPO}/issues/7"], issue_edit_args(REPO, 7)],
        {"body": f"New text\n\n{block}"},
        f"New text\n\n{block}",
        ["priority/p2-medium"],
        {RefineRecordKey.BODY_HASH: "b1"},
    )


def test_set_marks_body_replaces_the_text_and_keeps_the_marks_the_issue_holds() -> None:
    """The record block the issue holds now is kept, and the new marks join it (#4049)."""
    github, store = seeded(i7=("priority/p2-medium",))
    store.set_marks(read(store, 7), {RefineRecordKey.SECTION_HASH: "s1"})

    store.set_marks(read(store, 7), {RefineRecordKey.BODY_HASH: "b1"}, body="New text")

    item = read(store, 7)
    assert (store.read_issue_body(7), item.job_record, github.body(7).startswith("New text")) == (
        "New text",
        {RefineRecordKey.SECTION_HASH: "s1", RefineRecordKey.BODY_HASH: "b1"},
        True,
    )


def test_set_field_body_sends_one_patch_with_the_labels_the_body_and_the_record() -> None:
    """A field write with a body is still one `PATCH`: the labels, and the body with the block
    that holds the value and the marks (#4049)."""
    github, store = seeded(i7=("type/bug", "priority/p2-medium", "status/new"))
    item = read(store, 7)
    sent = len(github.calls)

    store.set_field(
        item, ItemField.STATUS, "Ready", marks={RefineRecordKey.BODY_HASH: "b1"}, body="New text"
    )

    patches = [args for args in github.writes() if "PATCH" in args]
    assert (
        github.calls[sent:],
        len(patches),
        sorted(json.loads(github.stdins[-1] or "{}")),
        github.labels(7),
        store.read_issue_body(7),
        read(store, 7).job_record,
    ) == (
        [["api", f"repos/{REPO}/issues/7"], issue_edit_args(REPO, 7)],
        1,
        ["body", "labels"],
        ["type/bug", "priority/p2-medium", "status/ready"],
        "New text",
        {ItemField.STATUS: "Ready", RefineRecordKey.BODY_HASH: "b1"},
    )


@pytest.mark.parametrize("adapter", ["memory", "github"])
def test_set_marks_body_keeps_the_text_when_no_body_is_given(adapter: str) -> None:
    """A write with no `body` leaves the text of the issue as it was, in each adapter (#4049)."""
    store: RoadmapStore
    if adapter == "memory":
        memory = InMemoryRoadmapStore(repo=REPO)
        memory.seed_issue("Text", body="Old text", labels=("priority/p2-medium",))
        store = memory
        number = 1
    else:
        _, store = seeded(i7=("priority/p2-medium",))
        number = 7

    store.set_marks(read(store, number), {RefineRecordKey.BODY_HASH: "b1"})

    assert (store.read_issue_body(number), read(store, number).job_record) == (
        "Old text" if adapter == "memory" else "Text",
        {RefineRecordKey.BODY_HASH: "b1"},
    )


def test_set_marks_body_in_memory_writes_the_body_with_the_marks() -> None:
    """The in-memory store carries a body with the marks in one write, as the GitHub store does,
    and keeps a job's entry for the body (#4049)."""
    memory = InMemoryRoadmapStore(repo=REPO)
    number = memory.seed_issue("Text", body="Old text", labels=("priority/p2-medium",))
    before = len(memory.writes)

    memory.set_marks(read(memory, number), {RefineRecordKey.BODY_HASH: "b1"}, body="New text")

    assert (
        memory.writes[before:],
        memory.read_issue_body(number),
        read(memory, number).job_record,
        [write.operation for write in memory.job_writes()],
    ) == (
        ["set_marks"],
        "New text",
        {RefineRecordKey.BODY_HASH: "b1"},
        ["write_issue_body", "set_mark"],
    )
