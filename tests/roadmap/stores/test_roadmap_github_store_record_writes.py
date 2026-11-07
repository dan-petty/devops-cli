"""The writes of an item that the GitHub roadmap store makes: fields, marks and the record block in
the body, in as few requests as it can (#1335).
"""

from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.exceptions.git import (
    GitHubOperationError,
)
from devops_cli.exceptions.roadmap import RoadmapItemChangedError
from devops_cli.roadmap.stores.github_store import (
    GitHubRoadmapStore,
    issue_edit_args,
)
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    Item,
    ItemField,
    RefineRecordKey,
)
from tests.support.builders import make_item
from tests.support.fakes.github import (
    API,
    RunnerSession,
)
from tests.support.fakes.github_repository import GitHubFake
from tests.support.roadmap_github_store import (
    OPEN_ISSUES,
    REPO,
    fake_store,
    labeled,
    read,
    recorded_store,
    seeded,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

_QUIET_SECONDS: float = 0.3
"""How long a test waits to verify that a competing write does not land during a held lock."""


RECORD = "<!-- devops-roadmap-record"


def test_a_field_write_reads_the_issue_then_patches_its_labels_and_body_in_one_request() -> None:
    """The field and its record go in one `PATCH`, so they never disagree (ADR 0016)."""
    github, store = seeded(i7=("type/bug", "priority/p2-medium", "status/new"))
    item = read(store, 7)
    sent = len(github.calls)
    store.set_field(item, ItemField.STATUS, "Ready")
    block = f'{RECORD} {{"Status": "Ready"}} -->'
    assert (
        github.calls[sent:],
        json.loads(github.stdins[-1] or "{}"),
        github.labels(7),
        github.body(7),
    ) == (
        [["api", f"repos/{REPO}/issues/7"], issue_edit_args(REPO, 7)],
        {"labels": ["type/bug", "priority/p2-medium", "status/ready"], "body": f"Text\n\n{block}"},
        ["type/bug", "priority/p2-medium", "status/ready"],
        f"Text\n\n{block}",
    )


def test_a_field_write_sets_marks_in_the_write_that_records_its_value() -> None:
    github, store = seeded(i7=("priority/p2-medium",))
    store.set_field(
        read(store, 7), ItemField.STATUS, "Ready", marks={RefineRecordKey.SECTION_HASH: "s1"}
    )
    patches = [args for args in github.writes() if "PATCH" in args]
    assert (len(patches), read(store, 7).job_record) == (
        1,
        {ItemField.STATUS: "Ready", RefineRecordKey.SECTION_HASH: "s1"},
    )


def test_set_marks_merges_the_marks_into_the_record_the_issue_holds_in_one_write() -> None:
    github = GitHubFake(REPO)
    github.seed_issue(
        7,
        labels=("priority/p2-medium",),
        body=f'Text\n\n{RECORD} {{"Status": "Ready", "refine.body_hash": "b0"}} -->',
    )
    store = fake_store(github)
    store.set_marks(
        read(store, 7), {RefineRecordKey.SECTION_HASH: "s1", RefineRecordKey.BODY_HASH: None}
    )
    assert (
        json.loads(github.stdins[-1] or "{}"),
        [args for args in github.writes()],
    ) == (
        {
            "body": f"Text\n\n{RECORD} "
            '{"Status": "Ready", "refine.body_hash": null, "refine.section_hash": "s1"} -->'
        },
        [issue_edit_args(REPO, 7)],
    )


def test_every_record_write_keeps_the_keys_this_version_does_not_know() -> None:
    """Another version's key survives this version's writes: none rebuilds the record from only
    the keys it read."""
    github = GitHubFake(REPO)
    github.seed_issue(
        7,
        labels=("priority/p2-medium",),
        body=f'{RECORD} {{"OtherFlag": "yes", "OtherTool": "x"}} -->',
    )
    store = fake_store(github)
    store.set_marks(read(store, 7), {RefineRecordKey.BODY_HASH: "b1"})
    store.set_field(read(store, 7), ItemField.PRIORITY, "P1-High")
    assert github.body(7) == (
        f'{RECORD} {{"OtherFlag": "yes", "OtherTool": "x", "Priority": "P1-High", '
        '"refine.body_hash": "b1"} -->'
    )


def test_a_record_value_with_the_end_of_a_comment_cannot_end_the_block() -> None:
    """Each `>` of the JSON is escaped, so a value such as a path ending in `-->` stays inside."""
    github, store = seeded(i7=("priority/p2-medium",))
    store.set_marks(read(store, 7), {RefineRecordKey.BLOCK_PATHS: "a-->b"})
    assert (github.body(7).count("-->"), read(store, 7).job_record) == (
        1,
        {RefineRecordKey.BLOCK_PATHS: "a-->b"},
    )


def test_the_stores_own_writes_keep_its_listing_of_every_issue_current() -> None:
    """A write keeps the issue GitHub returns, so the next read of every Item shows it with no
    second listing."""
    github, store = seeded(i7=("priority/p2-medium",), i8=("priority/p3-low",))
    (first, _) = store.items()
    store.set_field(first, ItemField.STATUS, "Ready")
    store.label_issue(8, "type/bug")
    listings = [args for args in github.calls if args[0].startswith(API)]
    assert (
        [(item.number, item.status, item.labels) for item in store.items()],
        len(listings),
    ) == (
        [
            (7, "Ready", ("priority/p2-medium", "status/ready")),
            (8, None, ("priority/p3-low", "type/bug")),
        ],
        1,
    )


def test_a_field_a_person_changed_after_the_read_raises_before_any_write() -> None:
    """The store read the issue, then a person set Priority: the job's Priority write, planned
    from that read, raises before any write and the person's value stays (ADR 0002)."""
    github, store = seeded(i7=("priority/p2-medium",))
    item = read(store, 7)
    github.issues[7]["labels"] = [{"name": "priority/p1-high"}]
    with pytest.raises(RoadmapItemChangedError, match="#7's Priority") as raised:
        store.set_field(item, ItemField.PRIORITY, "P3-Low")
    assert (
        github.writes(),
        github.labels(7),
        {key: raised.value.details[key] for key in ("field", "read", "now")},
    ) == ([], ["priority/p1-high"], {"field": "Priority", "read": "P2-Medium", "now": "P1-High"})


def _mark_refine(store: GitHubRoadmapStore, item: Item) -> None:
    store.set_marks(item, {RefineRecordKey.BODY_HASH: "b1"})


def _mark_refine_failure(store: GitHubRoadmapStore, item: Item) -> None:
    store.set_marks(item, {RefineRecordKey.FAILED_BODY_HASH: "f1"})


def _mark_implement(store: GitHubRoadmapStore, item: Item) -> None:
    store.set_marks(item, {ImplementRecordKey.JOB: "job-1"})


def _ready_with_refine_mark(store: GitHubRoadmapStore, item: Item) -> None:
    store.set_field(item, ItemField.STATUS, "Ready", marks={RefineRecordKey.BODY_HASH: "b1"})


def _write_body(store: GitHubRoadmapStore, item: Item) -> None:
    store.write_issue_body(item.number, "New text")


@pytest.mark.parametrize(
    ("held_write", "other_write", "record", "body"),
    [
        pytest.param(
            _mark_refine_failure,
            _mark_refine,
            {RefineRecordKey.BODY_HASH: "b1", RefineRecordKey.FAILED_BODY_HASH: "f1"},
            "Text",
            id="two-refine-marks",
        ),
        pytest.param(
            _ready_with_refine_mark,
            _mark_implement,
            {
                ItemField.STATUS: "Ready",
                RefineRecordKey.BODY_HASH: "b1",
                ImplementRecordKey.JOB: "job-1",
            },
            "Text",
            id="refine-field-write-then-implement-mark",
        ),
        pytest.param(
            _mark_implement,
            _ready_with_refine_mark,
            {
                ItemField.STATUS: "Ready",
                RefineRecordKey.BODY_HASH: "b1",
                ImplementRecordKey.JOB: "job-1",
            },
            "Text",
            id="implement-mark-then-refine-field-write",
        ),
        pytest.param(
            _write_body,
            _mark_implement,
            {ImplementRecordKey.JOB: "job-1"},
            "New text",
            id="body-write-then-implement-mark",
        ),
        pytest.param(
            _mark_implement,
            _write_body,
            {ImplementRecordKey.JOB: "job-1"},
            "New text",
            id="implement-mark-then-body-write",
        ),
    ],
)
def test_two_stores_writing_one_issue_at_once_keep_each_others_keys(
    held_write: Callable[[GitHubRoadmapStore, Item], None],
    other_write: Callable[[GitHubRoadmapStore, Item], None],
    record: dict[Any, str],
    body: str,
) -> None:
    """The Service's lanes each open a store for the repository, so two writes of one issue can
    overlap: the later write joins the record the earlier one wrote, never the one both read
    before either wrote (#1532). The model lane writes the refine, stage and alternatives keys,
    and the status lane writes the implement keys of the same Items (#2757)."""
    github, second_store = seeded(i7=("priority/p2-medium",))
    armed, read_done, writing, written = (threading.Event() for _ in range(4))
    handoffs: list[bool] = []

    def held_after_its_issue_read(
        args: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        answer = github(args, **kwargs)
        if armed.is_set() and args == ["api", f"repos/{REPO}/issues/7"] and not read_done.is_set():
            read_done.set()
            # Held between its read and its write: the other store's write lands here unless
            # the store keeps it out until this one writes. This short window checks that it
            # does not land, and opens only once the other store is about to write, so it
            # times the store's lock, not a thread start-up.
            handoffs.append(writing.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))
            written.wait(timeout=_QUIET_SECONDS)
        return answer

    first_store = GitHubRoadmapStore(
        REPO, runner=held_after_its_issue_read, session=RunnerSession(held_after_its_issue_read)
    )
    first_read, second_read = read(first_store, 7), read(second_store, 7)

    def write_other() -> None:
        handoffs.append(read_done.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))
        writing.set()
        other_write(second_store, second_read)
        written.set()

    writing_other = threading.Thread(target=write_other)
    armed.set()
    writing_other.start()
    held_write(first_store, first_read)
    writing_other.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    after = read(second_store, 7)
    assert (after.job_record, github.body(7).startswith(body), handoffs) == (
        record,
        True,
        [True, True],
    )


def test_a_body_write_reads_the_issue_and_writes_the_body_with_its_record() -> None:
    github = GitHubFake(REPO)
    block = f'{RECORD} {{"refine.body_hash": "b1"}} -->'
    github.seed_issue(7, labels=("priority/p2-medium",), body=f"Old\n\n{block}")
    store = fake_store(github)
    before = store.read_issue_body(7)
    sent = len(github.calls)
    store.write_issue_body(7, "New")
    assert (
        before,
        github.calls[sent:],
        json.loads(github.stdins[-1] or "{}"),
        store.read_issue_body(7),
    ) == (
        "Old",
        [["api", f"repos/{REPO}/issues/7"], issue_edit_args(REPO, 7)],
        {"body": f"New\n\n{block}"},
        "New",
    )


def test_a_body_or_field_write_to_a_pull_request_raises_without_writing() -> None:
    github = GitHubFake(REPO)
    github.seed_issue(918, labels=("priority/p1-high",), pull_request=True)
    store = fake_store(github)
    probe = make_item(number=918, title="#918")
    with pytest.raises(GitHubOperationError, match="#918 is not an issue"):
        store.read_issue_body(918)
    with pytest.raises(GitHubOperationError, match="#918 is not an issue"):
        store.write_issue_body(918, "content")
    with pytest.raises(GitHubOperationError, match="#918 is not an issue"):
        store.set_field(probe, ItemField.STATUS, "New")
    assert github.writes() == []


def test_a_failed_write_raises_and_names_the_issue() -> None:
    store, runner = recorded_store(
        {
            f"api repos/{REPO}/issues/917": labeled(OPEN_ISSUES[1], "priority/p2-medium"),
            "-X PATCH": (1, "gh: Validation Failed (HTTP 422)"),
        }
    )
    with pytest.raises(GitHubOperationError, match="Could not write issue #917"):
        store.set_field(read(store, 917), ItemField.STATUS, "Ready")
    assert runner.writes == [issue_edit_args(REPO, 917)]


def test_no_store_operation_sends_a_projects_request() -> None:
    """The store reads and writes Items through issues and their labels only (ADR 0016)."""
    github, store = seeded(i7=("priority/p2-medium",), i8=())
    item = read(store, 7)
    store.items()
    store.candidates()
    store.backlog()
    store.set_field(item, ItemField.STATUS, "Ready", marks={RefineRecordKey.BODY_HASH: "b"})
    store.set_marks(item, {RefineRecordKey.NEEDS_SPLIT: "1"})
    store.write_issue_body(7, "New")
    store.label_issue(8, "type/bug")
    store.comment(8, "Placed.")
    store.closures(8)
    assert (github.project_calls(), len(github.calls) > 10) == ([], True)
