"""The job record of an issue is the record that a job wrote for that issue (#7347).

A person can transfer an issue to another repository, and the issue keeps its body with the record
block. The record then names the branches and the pull requests of the repository that the issue
left. A job names each branch `<type>/<issue>-<slug>`, so a branch of the record tells the issue
number that the record was written for. A read gives a record only when no recorded branch names
another issue number, and one write replaces a record of another issue. The record of the issue
reads and is written as before.

GitHub is `GitHubFake`, a whole repository at the `gh` process edge.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.models.webhooks import WebhookIssue
from devops_cli.roadmap.stores.brain_issues import issue_from_event
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.store import (
    ItemField,
    RefineRecordKey,
    StageRecordKey,
    decode_job_record,
    encode_job_record,
    split_record,
)
from tests.support.fakes.github import RunnerSession
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

REPO = "example/other"
ITEM = ("priority/p2-medium", "status/new")
TEXT = "The text of the issue."
PENDING = '{"branch": "%s", "time": "2026-11-20T10:00:00+00:00"}'
# What a job of the repository `example/source` wrote for its issue 4107.
SOURCE_KEYS: dict[str, str] = {
    "Status": "Staged",
    "stage.branch": "feat/4107-add-the-rows",
    "stage.pr": "4110",
    "stage.ready": "4110",
    "stage.sha": "a" * 40,
    "implement.job": "devops-cli-implement-source-4107-0123456789",
    "refine.blocked_by": "4001",
    "alternatives.refs": "https://example.com/a",
    "another.version": "kept",
}


def _body(held: dict[str, Any]) -> str:
    """The body of an issue whose record block holds `held`."""
    return f"{TEXT}\n\n{encode_job_record(held, {})}"


def _held(body: str) -> dict[str, Any]:
    """The JSON object of the record block of `body`."""
    return split_record(body)[1]


def _store(github: GitHubFake) -> GitHubRoadmapStore:
    return GitHubRoadmapStore(github.repo, runner=github, session=RunnerSession(github))


def _seeded(held: dict[str, Any], *, number: int = 7) -> tuple[GitHubFake, GitHubRoadmapStore]:
    """The repository `REPO` with item `number`, whose body holds the record `held`."""
    github = GitHubFake(REPO)
    github.seed_issue(number, labels=ITEM, body=_body(held))
    return github, _store(github)


# ── The read ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "held",
    [
        {"stage.branch": "feat/4107-add-the-rows", "stage.pr": "4110"},
        {"implement.branch": "fix/4107-add-the-rows", "implement.pr": "4110"},
        {"stage.pending": PENDING % "feat/4107-add-the-rows", "refine.body_hash": "b0"},
    ],
    ids=["stage.branch", "implement.branch", "stage.pending"],
)
def test_a_record_whose_branch_names_another_issue_number_reads_as_empty(
    held: dict[str, str],
) -> None:
    assert decode_job_record(held, issue="#7", number=7) == {}


def test_a_record_whose_branches_name_the_issue_reads_as_before() -> None:
    held = {
        "Status": "Staged",
        "stage.branch": "feat/7-add-the-rows",
        "stage.pr": "12",
        "stage.pending": PENDING % "feat/7-add-the-rows",
        "implement.branch": "feat/7-add-the-rows",
        "refine.body_hash": "b0",
    }
    assert decode_job_record(held, issue="#7", number=7) == decode_job_record(held)


def test_a_record_that_names_no_branch_reads_as_before() -> None:
    held = {"Status": "Ready", "stage.pr": "12", "refine.body_hash": "b0"}
    assert decode_job_record(held, issue="#7", number=7) == decode_job_record(held)


def test_a_branch_that_names_no_issue_number_does_not_empty_the_record() -> None:
    held = {"stage.branch": "main", "refine.body_hash": "b0"}
    assert decode_job_record(held, issue="#7", number=7) == {
        StageRecordKey.BRANCH: "main",
        RefineRecordKey.BODY_HASH: "b0",
    }


# ── Each reader ───────────────────────────────────────────────────────────────


def _github_item(held: dict[str, Any]) -> tuple[dict[Any, Any], bool]:
    """What the GitHub store reads for one item: from one read of the issue."""
    _, store = _seeded(held)
    item = store.item(7)
    assert item is not None
    return dict(item.job_record), item.foreign_record


def _github_listing(held: dict[str, Any]) -> tuple[dict[Any, Any], bool]:
    """What the GitHub store reads for one item: from the listing of every issue."""
    _, store = _seeded(held)
    (item,) = store.items()
    return dict(item.job_record), item.foreign_record


def _event(held: dict[str, Any]) -> tuple[dict[Any, Any], bool]:
    """What the brain keeps for the issue of an issue event."""
    issue = WebhookIssue(number=7, title="An item", body=_body(held))
    record = issue_from_event(REPO, issue).record
    return dict(record.job_record), record.foreign_record


def _memory(held: dict[str, Any]) -> tuple[dict[Any, Any], bool]:
    """What the in-memory store reads for one item."""
    store = InMemoryRoadmapStore(repo=REPO)
    number = store.seed_issue("An item", labels=ITEM, body=_body(held))
    item = store.item(number)
    assert item is not None
    return dict(item.job_record), item.foreign_record


READERS = pytest.mark.parametrize(
    "reader", [_github_item, _github_listing, _event, _memory], ids=lambda reader: reader.__name__
)


@READERS
def test_a_record_whose_branch_names_another_issue_is_empty_for_each_reader(reader: Any) -> None:
    assert reader(SOURCE_KEYS) == ({}, True)


@READERS
def test_a_record_whose_branch_names_the_issue_keeps_each_value_for_each_reader(
    reader: Any,
) -> None:
    number = 1 if reader is _memory else 7
    held = {"Status": "New", "stage.branch": f"feat/{number}-add-the-rows", "stage.pr": "12"}
    assert reader(held) == (
        {
            ItemField.STATUS: "New",
            StageRecordKey.BRANCH: f"feat/{number}-add-the-rows",
            StageRecordKey.PR: "12",
        },
        False,
    )


# ── The write ─────────────────────────────────────────────────────────────────


def test_a_write_to_the_record_of_the_issue_gives_the_block_as_before() -> None:
    """The body after a mark write is the text and the block that `encode_job_record` gives for
    the record of the issue with the mark: each key stays, and the block gets no other key."""
    held = {
        "Status": "New",
        "stage.branch": "feat/7-add-the-rows",
        "stage.pr": "12",
        "another.version": "kept",
    }
    github, store = _seeded(held)
    item = store.item(7)
    assert item is not None
    store.set_marks(item, {StageRecordKey.READY: "12"})
    assert github.body(7) == f"{TEXT}\n\n{encode_job_record(held, {'stage.ready': '12'})}"


def test_one_write_replaces_a_record_that_was_written_for_another_issue() -> None:
    """The write merges into no key of the old record: the block holds the keys of the write, and
    no more."""
    github, store = _seeded(SOURCE_KEYS)
    item = store.item(7)
    assert item is not None
    store.set_marks(item, {RefineRecordKey.BODY_HASH: "b1"})
    after = store.item(7, fresh=True)
    assert after is not None
    assert (_held(github.body(7)), dict(after.job_record), after.foreign_record) == (
        {"refine.body_hash": "b1"},
        {RefineRecordKey.BODY_HASH: "b1"},
        False,
    )


def test_a_write_with_no_mark_takes_the_record_of_another_issue_out_of_the_body() -> None:
    github, store = _seeded(SOURCE_KEYS)
    item = store.item(7)
    assert item is not None
    store.set_marks(item, {})
    assert (github.body(7), len(github.writes())) == (TEXT, 1)


def test_a_field_write_replaces_a_record_that_was_written_for_another_issue() -> None:
    github, store = _seeded(SOURCE_KEYS)
    item = store.item(7)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "Ready")
    assert (_held(github.body(7)), github.labels(7)) == (
        {"Status": "Ready"},
        ["priority/p2-medium", "status/ready"],
    )


def test_the_in_memory_store_replaces_a_record_of_another_issue_as_the_github_store_does() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    number = store.seed_issue("An item", labels=ITEM, body=_body(SOURCE_KEYS))
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {RefineRecordKey.BODY_HASH: "b1"})
    assert _held(store.raw_body(number)) == {"refine.body_hash": "b1"}
