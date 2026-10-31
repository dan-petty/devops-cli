"""GitHub roadmap store over a stub runner that answers with recorded `gh` output (ADR 0016).

The recorded listings under `tests/fixtures/roadmap/` come from dan-petty/devops-cli, trimmed to
the keys the store reads; a case adds the labels and bodies it needs to a copy. The milestone
listing keeps the recorded milestones that name a past version, and adds two planning buckets,
#47 `2026-10-29` with a due date and #48 `Q4 hardening` without one. The store reads its REST
listings through the GitHub session (#983): `recorded_store` answers them from the same recorded
replies through `RunnerSession`, and the tests of paging, early stops and failed pages run the
real session over the `github_api` fake (`over_github`). The writes run over `GitHubFake`, the
`gh` process edge of a whole repository. No case runs `gh` or opens a socket.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import threading
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from typing import Any, NoReturn
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest

from devops_cli.exceptions.git import (
    GitHubFileNotFoundError,
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.exceptions.roadmap import RoadmapItemChangedError
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.github_store import (
    GitHubRoadmapStore,
    is_private_args,
    issue_edit,
    issue_edit_args,
)
from devops_cli.roadmap.store import (
    ChangeKind,
    CloseReason,
    Evidence,
    EvidenceKind,
    GitHubState,
    ImplementRecordKey,
    Item,
    ItemField,
    RefineRecordKey,
    RepositoryFacts,
    RoadmapStore,
)
from tests.roadmap_github_fake import GitHubFake
from tests.support.fakes.github import (
    API,
    JSON_TYPE,
    GitHubApiFake,
    RunnerSession,
    github_json,
    next_page,
    quota_headers,
)
from tests.support.paths import FIXTURES
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

_QUIET_SECONDS: float = 0.3
"""How long a test waits to verify that a competing write does not land during a held lock."""

ROADMAP_FIXTURES = FIXTURES / "roadmap"
REPO = "dan-petty/devops-cli"
ISSUE_URL = f"https://github.com/{REPO}/issues"
RECORD = "<!-- devops-roadmap-record"


def recorded(name: str) -> Any:
    return json.loads((ROADMAP_FIXTURES / name).read_text(encoding="utf-8"))


MILESTONES = recorded("milestones.json")
ISSUES_IN_MILESTONE = recorded("issues-milestone-43.json")
OPEN_ISSUES = recorded("issues-open.json")
EVENTS = recorded("issue-events.json")

LISTING_MILESTONES = f"repos/{REPO}/milestones?state=all&per_page=100"
LISTING_IN_MILESTONE = f"repos/{REPO}/issues?milestone=43&state=all&per_page=100"


def created_milestone(number: int, title: str, **changes: Any) -> dict[str, Any]:
    """The recorded milestone #43, as GitHub would return it after a write."""
    milestone = next(m for m in MILESTONES if m["title"] == "v0.2.25")
    return {**milestone, "number": number, "title": title, **changes}


def labeled(payload: dict[str, Any], *labels: str, **changes: Any) -> dict[str, Any]:
    """A copy of a recorded issue with `labels` added to its own, and `changes` made."""
    copy: dict[str, Any] = deepcopy(payload)
    copy["labels"] = [*copy["labels"], *({"name": label} for label in labels)]
    return {**copy, **changes}


class RecordedGh:
    """A gh runner that answers each command from recorded output and keeps every call.

    A reply that is a function is called with the command's argv, so a write can change what a
    later read returns.
    """

    def __init__(self, replies: dict[str, Any]) -> None:
        self.replies = replies
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((args, kwargs))
        command = " ".join(args)
        key = next((key for key in self.replies if key in command), None)
        assert key is not None, f"no recorded reply for: {command}"
        reply = self.replies[key]
        reply = reply(args) if callable(reply) else reply
        returncode, output = reply if isinstance(reply, tuple) else (0, reply)
        text = output if isinstance(output, str) else json.dumps(output)
        return subprocess.CompletedProcess(args, returncode, text, "" if returncode == 0 else text)

    @property
    def writes(self) -> list[list[str]]:
        """The calls that change GitHub."""
        return [args for args, _ in self.calls if {"POST", "PATCH", "DELETE"} & set(args)]


def recorded_store(replies: dict[str, Any]) -> tuple[GitHubRoadmapStore, RecordedGh]:
    runner = RecordedGh(replies)
    return GitHubRoadmapStore(REPO, runner=runner, session=RunnerSession(runner)), runner


def fake_store(github: GitHubFake) -> GitHubRoadmapStore:
    """The store over the whole repository `github` fakes at the `gh` process edge."""
    return GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github))


def seeded(**issues: tuple[str, ...]) -> tuple[GitHubFake, GitHubRoadmapStore]:
    """A repository whose issue `#<n>`, keyed `i<n>`, holds the labels given, and its store."""
    github = GitHubFake(REPO)
    for key, labels in issues.items():
        github.seed_issue(int(key.removeprefix("i")), labels=labels, body="Text")
    return github, fake_store(github)


def read(store: RoadmapStore, number: int) -> Item:
    found = store.item(number)
    assert found is not None
    return found


# ── Milestones ────────────────────────────────────────────────────────────────


def test_a_milestone_is_found_by_its_exact_title_or_by_its_number() -> None:
    """No title is read as a version: `0.2.25` names no milestone, `v0.2.25` and `43` name #43."""
    store, _ = recorded_store({"milestones?state=all": MILESTONES})
    found = (store.milestone("v0.2.25"), store.milestone("43"), store.milestone("0.2.25"))
    assert [milestone.number if milestone else None for milestone in found] == [43, 43, None]


def test_milestones_sort_by_due_date_then_by_number_whatever_their_titles() -> None:
    """Every recorded milestone is read, whatever its title; the one with a due date comes
    first, and the others follow by number."""
    store, _ = recorded_store({"milestones?state=all": MILESTONES})
    milestones = store.milestones()
    numbers = [milestone.number for milestone in milestones]
    assert (
        (milestones[0].title, milestones[0].due_on),
        numbers[1:] == sorted(numbers[1:]),
        "Q4 hardening" in [milestone.title for milestone in milestones],
        len(milestones),
    ) == (("2026-10-29", date(2026, 10, 29)), True, True, len(MILESTONES))


def test_edit_milestone_sends_only_the_fields_it_is_given() -> None:
    store, runner = recorded_store(
        {"milestones?state=all": MILESTONES, "-X PATCH": created_milestone(43, "2026-12-24")}
    )
    store.edit_milestone("v0.2.25", title="2026-12-24", due_on=date(2026, 12, 24))
    assert runner.writes == [
        [
            "api",
            "-X",
            "PATCH",
            f"repos/{REPO}/milestones/43",
            "-f",
            "title=2026-12-24",
            "-f",
            "due_on=2026-12-24T00:00:00Z",
        ]
    ]


def test_renaming_a_milestone_onto_another_milestones_title_raises_without_writing() -> None:
    store, runner = recorded_store({"milestones?state=all": MILESTONES})
    with pytest.raises(GitHubOperationError, match="already has the title 'Q4 hardening'"):
        store.edit_milestone("43", title="Q4 hardening")
    assert runner.writes == []


def test_an_edit_that_names_no_state_sends_no_state() -> None:
    store, runner = recorded_store(
        {"milestones?state=all": MILESTONES, "-X PATCH": created_milestone(43, "v0.2.25")}
    )
    edited = store.edit_milestone("43", description="new text")
    assert (runner.writes, edited.state) == (
        [["api", "-X", "PATCH", f"repos/{REPO}/milestones/43", "-f", "description=new text"]],
        GitHubState.OPEN,
    )


def test_an_edit_with_nothing_to_change_writes_nothing() -> None:
    store, runner = recorded_store({"milestones?state=all": MILESTONES})
    assert (store.edit_milestone("43").number, runner.writes) == (43, [])


def test_close_milestone_patches_only_its_state() -> None:
    store, runner = recorded_store(
        {
            "milestones?state=all": MILESTONES,
            "-X PATCH": created_milestone(48, "Q4 hardening", state="closed"),
        }
    )
    closed = store.close_milestone("Q4 hardening")
    assert (runner.writes, closed.state) == (
        [["api", "-X", "PATCH", f"repos/{REPO}/milestones/48", "-f", "state=closed"]],
        GitHubState.CLOSED,
    )


def test_editing_an_unknown_milestone_raises_without_writing() -> None:
    store, runner = recorded_store({"milestones?state=all": MILESTONES})
    with pytest.raises(GitHubOperationError, match="No milestone has the title or number"):
        store.close_milestone("Q5")
    assert runner.writes == []


# ── Items and Candidates ──────────────────────────────────────────────────────


def test_items_in_a_milestone_take_their_fields_from_their_labels_and_state_from_rest() -> None:
    """A closed issue is an Item too: its state, milestone and fields come from the listing."""
    listing = [
        *ISSUES_IN_MILESTONE[:2],
        labeled(ISSUES_IN_MILESTONE[2], "priority/p1-high", "status/in-progress"),
        ISSUES_IN_MILESTONE[3],
    ]
    store, runner = recorded_store({"issues?milestone=43": listing})
    items = store.items(milestone=43)
    assert (
        [
            (item.number, item.state, item.state_reason, item.milestone, item.status, item.priority)
            for item in items
        ],
        [args for args, _ in runner.calls],
    ) == (
        [(737, GitHubState.CLOSED, "completed", "v0.2.25", "In Progress", "P1-High")],
        [[f"{API}/{LISTING_IN_MILESTONE}"]],
    )


def test_backlog_reads_the_open_issues_in_no_milestone() -> None:
    open_placed = labeled(ISSUES_IN_MILESTONE[1], "priority/p2-medium", milestone=None)
    store, runner = recorded_store({"issues?milestone=none": [open_placed]})
    assert ([item.number for item in store.backlog()], [args for args, _ in runner.calls]) == (
        [739],
        [[f"{API}/repos/{REPO}/issues?milestone=none&state=open&per_page=100"]],
    )


def test_items_carry_the_body_of_the_listing_they_were_read_from_with_no_request_per_issue() -> (
    None
):
    """The recorded listings hold no body, so one is put into a copy of each (#1539)."""
    in_milestone = labeled(ISSUES_IN_MILESTONE[2], "priority/p1-high", body="Planned text")
    in_backlog = labeled(
        ISSUES_IN_MILESTONE[1], "priority/p2-medium", milestone=None, body="Backlog text"
    )
    store, runner = recorded_store(
        {"issues?milestone=43": [in_milestone], "issues?milestone=none": [in_backlog]}
    )
    planned, backlog = store.items(milestone=43), store.backlog()
    assert (
        [(item.number, item.body) for item in planned],
        [(item.number, item.body) for item in backlog],
        [args[0] for args, _ in runner.calls],
    ) == (
        [(737, "Planned text")],
        [(739, "Backlog text")],
        [
            f"{API}/{LISTING_IN_MILESTONE}",
            f"{API}/repos/{REPO}/issues?milestone=none&state=open&per_page=100",
        ],
    )


def test_candidates_drop_a_pull_request_a_closed_issue_and_an_issue_with_a_priority() -> None:
    # The recorded pull request #918 had merged; it is reopened here, so only its
    # `pull_request` key can keep it out.
    listing = [
        {**OPEN_ISSUES[0], "state": "open"},
        labeled(OPEN_ISSUES[1], "priority/p2-medium"),
        OPEN_ISSUES[2],
        ISSUES_IN_MILESTONE[3],
    ]
    store, _ = recorded_store({"issues?state=all": listing})
    assert [(c.number, c.labels) for c in store.candidates()] == [
        (916, ("type/bug", "scope/security"))
    ]


def test_the_items_are_the_issues_with_a_priority_label() -> None:
    listing = [
        labeled(ISSUES_IN_MILESTONE[0], "priority/p2-medium"),
        ISSUES_IN_MILESTONE[1],
        labeled(ISSUES_IN_MILESTONE[2], "priority/p3-low"),
        labeled(OPEN_ISSUES[0], "priority/p1-high"),
    ]
    store, _ = recorded_store({"issues?state=all": listing})
    assert [(item.number, item.state, item.priority) for item in store.items()] == [
        (737, GitHubState.CLOSED, "P3-Low"),
        (768, GitHubState.OPEN, "P2-Medium"),
    ]


def test_an_item_is_one_read_of_its_issue_and_none_for_an_issue_that_is_no_item() -> None:
    store, runner = recorded_store(
        {
            "issues/737": labeled(ISSUES_IN_MILESTONE[2], "priority/p1-high"),
            "issues/739": ISSUES_IN_MILESTONE[1],
            "issues/918": labeled(OPEN_ISSUES[0], "priority/p1-high"),
            "issues/99": (1, "gh: Not Found (HTTP 404)"),
        }
    )
    found = [store.item(number) for number in (737, 739, 918, 99)]
    assert (
        [item.number if item else None for item in found],
        [args for args, _ in runner.calls],
    ) == (
        [737, None, None, None],
        [["api", f"repos/{REPO}/issues/{number}"] for number in (737, 739, 918, 99)],
    )


def test_the_listing_of_every_issue_is_read_once_for_the_stores_life() -> None:
    """`items()`, `issues()` and `candidates()` share one read (#1361)."""
    store, runner = recorded_store({"issues?state=all": ISSUES_IN_MILESTONE + OPEN_ISSUES})
    store.items()
    store.issues()
    store.candidates()
    store.items()
    assert [args for args, _ in runner.calls] == [
        [f"{API}/repos/{REPO}/issues?state=all&per_page=100"]
    ]


def test_items_carry_the_known_keys_of_the_record_block_in_their_body() -> None:
    """A key this version does not know, such as one another version writes, is left out: an
    `OtherTool` mark reads as nothing, and the body reads without the block."""
    block = '<!-- devops-roadmap-record {"OtherTool": "y", "Priority": "P1-High"} -->'
    listing = [labeled(ISSUES_IN_MILESTONE[0], "priority/p1-high", body=f"Text\n\n{block}")]
    store, _ = recorded_store({"issues?state=all": listing})
    assert [(item.number, item.body, item.job_record) for item in store.items()] == [
        (768, "Text", {ItemField.PRIORITY: "P1-High"})
    ]


# ── Item writes ───────────────────────────────────────────────────────────────


def test_a_value_that_is_not_a_field_value_raises_before_any_request() -> None:
    github, store = seeded(i7=("priority/p2-medium",))
    item = read(store, 7)
    sent = len(github.calls)
    with pytest.raises(GitHubOperationError, match="'P9-Someday' is not a Priority value"):
        store.set_field(item, ItemField.PRIORITY, "P9-Someday")
    assert github.calls[sent:] == []


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
    probe = Item(number=918, title="#918", url=f"{ISSUE_URL}/918")
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


# ── Failed reads ──────────────────────────────────────────────────────────────


def over_github(replies: dict[str, Any] | None = None) -> tuple[GitHubRoadmapStore, RecordedGh]:
    """The store whose REST listings the process's GitHub session reads from the `github_api`
    fake, and whose gh commands `replies` answer (#983)."""
    runner = RecordedGh(replies or {})
    return GitHubRoadmapStore(REPO, runner=runner, session=get_github_session()), runner


def test_a_listing_github_fails_raises_the_sessions_unread_error_naming_it(
    github_api: GitHubApiFake,
) -> None:
    """A listing GitHub answers with a 502 through the session's retries raises the session's
    unread error, naming the listing and the status; no gh command runs (#983)."""
    github_api.route("GET", f"/{LISTING_MILESTONES}", github_json({"message": "x"}, status=502))
    store, runner = over_github()
    with pytest.raises(GitHubUnreadError) as raised:
        store.milestones()
    details = raised.value.details
    assert (details["path"], details["status"], runner.calls) == (
        f"/{LISTING_MILESTONES}",
        502,
        [],
    )


def test_a_rate_limited_listing_raises_rate_limit_error(github_api: GitHubApiFake) -> None:
    """A listing GitHub refuses for a spent quota raises the rate limit, which stops an intake
    round."""
    github_api.route(
        "GET",
        f"/{LISTING_MILESTONES}",
        github_json({"message": "rate"}, status=403, headers=quota_headers(0, reset_in=30.0)),
    )
    store, _ = over_github()
    with pytest.raises(GitHubRateLimitError) as raised:
        store.milestones()
    assert raised.value.error_code == "GITHUB_RATE_LIMIT_UNKNOWN"


def test_a_failed_gh_read_raises_and_names_the_read() -> None:
    store, _ = recorded_store({"contents/notes.md": (1, "HTTP 502: Bad Gateway")})
    with pytest.raises(GitHubOperationError, match=r"Could not read notes\.md"):
        store.repository_file("notes.md")


@pytest.mark.parametrize(
    ("said", "error"),
    [
        pytest.param("gh: Too Many Requests (HTTP 429)", GitHubRateLimitError, id="429"),
        pytest.param(
            "You have exceeded a secondary rate limit.", GitHubRateLimitError, id="secondary"
        ),
        pytest.param("gh: Bad credentials (HTTP 401)", GitHubUnauthenticatedError, id="401"),
    ],
)
def test_a_failed_read_raises_the_class_the_gh_classifier_names(
    said: str, error: type[GitHubOperationError]
) -> None:
    """A failed gh read raises what `classify_gh_failure` makes of gh's output (#983), not only
    the rate limits the store once matched itself, with gh's exit status as an int."""
    store, _ = recorded_store({"contents/notes.md": (1, said)})
    with pytest.raises(GitHubOperationError) as raised:
        store.repository_file("notes.md")
    assert (type(raised.value), raised.value.details["exit_code"]) == (error, 1)


_PARTIAL_GRAPHQL_ANSWER = (
    '{{"data": {{"repository": {{"issues": {{"nodes": [{{"number": 705, "title": "{title}"}}]}}}}}},'
    ' "errors": [{{"type": "FORBIDDEN", "message": "Resource not accessible by integration"}}]}}'
)


@pytest.mark.parametrize(
    "title",
    [
        "correct secondary-limit backoff and retry-after handling in run_gh",
        "verify read:project scope",
        "HTTP 401 Bad credentials",
        "not logged in",
        "unknown owner type",
    ],
)
def test_a_failed_read_classifies_gh_s_stderr_never_the_titles_on_stdout(title: str) -> None:
    """gh copies GitHub's partial answer, item titles included, to stdout and writes only
    `gh: <message>` to stderr; a title that reads like a rate limit, a scope or a refused login
    is GitHub's data, so the read fails as a failed read (#983). `RecordedGh` writes one text to
    both streams, so this runner writes each its own."""

    def gh(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        body = _PARTIAL_GRAPHQL_ANSWER.format(title=title)
        return subprocess.CompletedProcess(
            args, 1, body, "gh: Resource not accessible by integration"
        )

    store = GitHubRoadmapStore(REPO, runner=gh)
    with pytest.raises(GitHubOperationError) as raised:
        store.repository_file("notes.md")
    assert (type(raised.value), "Could not read notes.md" in raised.value.message) == (
        GitHubOperationError,
        True,
    )


def test_a_listing_entry_that_is_not_the_shape_the_store_reads_raises() -> None:
    store, _ = recorded_store({"milestones?state=all": [{"number": 1}]})
    with pytest.raises(GitHubOperationError, match="malformed milestones"):
        store.milestones()


def test_an_error_object_where_a_listing_belongs_raises() -> None:
    store, _ = recorded_store({"issues?state=all": {"message": "Not Found"}})
    with pytest.raises(GitHubUnreadError, match="not a JSON array"):
        store.candidates()


# ── Paging and caching ────────────────────────────────────────────────────────


def test_every_rest_listing_is_read_through_the_session_a_full_page_at_a_time() -> None:
    """Each REST listing is read through the GitHub session at a full page, which follows
    GitHub's links itself; none goes through gh (#983)."""
    store, runner = recorded_store(
        {
            "milestones?state=all": MILESTONES,
            "issues?milestone=43": ISSUES_IN_MILESTONE,
            "issues?milestone=none": [],
            "issues?state=": OPEN_ISSUES,
        }
    )
    store.milestones()
    store.items(milestone=43)
    store.items()
    store.backlog()
    store.candidates()
    listings = [args for args, _ in runner.calls if args[0].startswith(API)]
    gh_listings = [args for args, _ in runner.calls if args[:2] == ["api", f"repos/{REPO}"]]
    assert (
        [len(args) for args in listings],
        [_query(args, "per_page", "page") for args in listings],
        gh_listings,
    ) == ([1] * 4, [(["100"], [])] * 4, [])


def _query(args: list[str], *names: str) -> tuple[list[str], ...]:
    """The values of `names` in the query of the URL or endpoint a REST read names last."""
    query = parse_qs(urlsplit(args[-1]).query)
    return tuple(query.get(name, []) for name in names)


LISTINGS: list[tuple[str, Any, Callable[[GitHubRoadmapStore], object]]] = [
    (f"/{LISTING_MILESTONES}", MILESTONES[0], lambda store: store.milestones()),
    (f"/repos/{REPO}/issues?state=all&per_page=100", OPEN_ISSUES[1], lambda store: store.issues()),
    (
        f"/repos/{REPO}/issues/844/comments?per_page=100",
        recorded("issue-844-comments.json")[0],
        lambda store: store.comments_on(844),
    ),
]
_HTML = httpx2.Response(
    200, headers={"content-type": "text/html; charset=utf-8"}, content=b"<html>upstream</html>"
)


@pytest.mark.parametrize("bad", [1, 2], ids=["first-page", "later-page"])
@pytest.mark.parametrize(
    "answer",
    [
        _HTML,
        httpx2.Response(200, headers={"content-type": JSON_TYPE}),
        github_json({"message": "x"}),
    ],
    ids=["html", "empty", "object"],
)
@pytest.mark.parametrize(
    ("path", "full", "read_listing"),
    LISTINGS,
    ids=["milestones", "issues", "comments"],
)
def test_a_listing_page_that_is_not_a_json_list_raises_naming_it(
    github_api: GitHubApiFake,
    path: str,
    full: Any,
    read_listing: Callable[[GitHubRoadmapStore], object],
    answer: httpx2.Response,
    bad: int,
) -> None:
    """The reviewers' replay: a page answered with a body that is not a JSON list, such as a
    proxy's HTML, read as the end of the listing, so a bad first page gave an empty listing and
    a bad later page a short one. The session raises, naming the listing and the page, before
    any write, and requests no page after it."""
    later = f"{path}&page=2"
    github_api.route(
        "GET", path, answer if bad == 1 else github_json([full] * 100, headers=next_page(later))
    )
    github_api.route("GET", later, answer)
    store, runner = over_github()
    with pytest.raises(GitHubUnreadError) as raised:
        read_listing(store)
    assert (
        (raised.value.details["path"], raised.value.details["page"]),
        len(github_api.sent),
        runner.writes,
    ) == ((path, bad), bad, [])


def test_a_listing_reads_on_while_github_links_a_next_page(github_api: GitHubApiFake) -> None:
    """The session follows each page's `rel="next"`: two linked pages of a hundred issues are
    two requests and two hundred issues, and the second page, which links none, ends the read."""
    first = f"/repos/{REPO}/issues?state=all&per_page=100"
    second = f"{first}&page=2"
    issues = [issue_payload(number) for number in range(1, 201)]
    github_api.route("GET", first, github_json(issues[:100], headers=next_page(second)))
    github_api.route("GET", second, github_json(issues[100:]))
    store, _ = over_github()
    assert (len(store.issues()), len(github_api.sent)) == (200, 2)


def test_every_read_and_write_passes_use_cache_false() -> None:
    issue = labeled(ISSUES_IN_MILESTONE[2], "priority/p1-high")
    store, runner = recorded_store(
        {
            "milestones?state=all": MILESTONES,
            "issues?milestone=43": ISSUES_IN_MILESTONE,
            "-X PATCH": issue,
            "issues/737": issue,
            "issues?state=all": OPEN_ISSUES,
            "issues/events": EVENTS,
        }
    )
    store.items(milestone=43)
    item = read(store, 737)
    store.candidates()
    store.changes_since(datetime(2026, 10, 1, tzinfo=UTC))
    store.set_field(item, ItemField.STATUS, "Ready")
    assert ([kwargs["use_cache"] for _, kwargs in runner.calls], len(runner.calls)) == (
        [False] * 6,
        6,
    )


# ── Changes ───────────────────────────────────────────────────────────────────


def event_at(template: dict[str, Any], moment: datetime) -> dict[str, Any]:
    return {**template, "created_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ")}


EVENTS_LISTING = f"/repos/{REPO}/issues/events?per_page=100"


def test_changes_since_follows_newest_first_pages_and_stops_at_the_first_older_event(
    github_api: GitHubApiFake,
) -> None:
    """The issue events are read newest first through the session, following GitHub's links,
    and the read stops at the first event older than the cutoff: the third page is never
    requested."""
    referenced = next(event for event in EVENTS if event["event"] == "referenced")
    start = datetime(2026, 10, 3, tzinfo=UTC)
    newer_page = [event_at(referenced, start - timedelta(minutes=n)) for n in range(100)]
    oldest_recorded = datetime.fromisoformat(EVENTS[-1]["created_at"])
    older_padding = [
        event_at(referenced, oldest_recorded - timedelta(minutes=n + 1)) for n in range(90)
    ]
    second, third = f"{EVENTS_LISTING}&page=2", f"{EVENTS_LISTING}&page=3"
    github_api.route("GET", EVENTS_LISTING, github_json(newer_page, headers=next_page(second)))
    github_api.route("GET", second, github_json(EVENTS + older_padding, headers=next_page(third)))
    github_api.route("GET", third, github_json({"message": "page 3 must not be read"}, status=500))
    store, _ = over_github()
    changes = store.changes_since(datetime(2026, 10, 1, 22, 0, tzinfo=UTC))
    assert (
        [url for url in github_api.requested if "issues/events" in url],
        [(change.kind, change.number, change.at.isoformat()) for change in changes],
    ) == (
        [f"GET {API}{EVENTS_LISTING}", f"GET {API}{second}"],
        [
            (ChangeKind.CLOSED, 299, "2026-10-01T22:39:06+00:00"),
            (ChangeKind.LABELED, 917, "2026-10-01T22:39:11+00:00"),
        ],
    )


def test_changes_since_whose_second_event_is_older_than_the_cutoff_sends_one_request(
    github_api: GitHubApiFake,
) -> None:
    """The events' second entry is older than the cutoff, and GitHub links a next page: the
    read stops there, so the events cost one request and the linked page is never asked for."""
    referenced = next(event for event in EVENTS if event["event"] == "referenced")
    cutoff = datetime(2026, 10, 2, tzinfo=UTC)
    page = [
        event_at(referenced, cutoff + timedelta(minutes=5)),
        event_at(referenced, cutoff - timedelta(minutes=5)),
    ]
    second = f"{EVENTS_LISTING}&page=2"
    github_api.route("GET", EVENTS_LISTING, github_json(page, headers=next_page(second)))
    github_api.route("GET", second, github_json({"message": "must not be read"}, status=500))
    store, _ = over_github()
    store.changes_since(cutoff)
    assert [url for url in github_api.requested if "issues/events" in url] == [
        f"GET {API}{EVENTS_LISTING}"
    ]


def test_changes_since_keeps_label_and_state_events_only() -> None:
    """A milestone event is a person's planning and no job reads it, so the poll reports none.
    A field change is a label event of its family (ADR 0003)."""
    closed = next(e for e in EVENTS if e["event"] == "closed" and "pull_request" not in e["issue"])
    reopened = {**closed, "event": "reopened", "created_at": "2026-10-02T01:00:00Z"}
    store, _ = recorded_store({"issues/events": [reopened, *EVENTS]})
    changes = store.changes_since(datetime(2026, 10, 1))
    assert [(change.kind, change.number, change.actor, change.label) for change in changes] == [
        (ChangeKind.UNLABELED, 829, "dan-petty", "scope/github"),
        (ChangeKind.CLOSED, 299, "dan-petty", None),
        (ChangeKind.LABELED, 917, "dan-petty", "type/bug"),
        (ChangeKind.REOPENED, 299, "dan-petty", None),
    ]


def test_changes_since_drops_an_actors_own_changes() -> None:
    """A run's own events are left out, and the others' changes stay (#1361)."""
    closed = next(e for e in EVENTS if e["event"] == "closed" and "pull_request" not in e["issue"])
    own = {**closed, "actor": {"login": "roadmap-bot"}, "created_at": "2026-10-02T01:00:00Z"}
    store, runner = recorded_store({"issues/events": [own]})
    alone = store.changes_since(datetime(2026, 10, 1, tzinfo=UTC), except_actor="roadmap-bot")
    runner.replies["issues/events"] = [own, *EVENTS]
    mixed = store.changes_since(datetime(2026, 10, 1, tzinfo=UTC), except_actor="roadmap-bot")
    assert (alone, {change.actor for change in mixed}, len(mixed)) == ([], {"dan-petty"}, 3)


def test_changes_since_with_an_empty_actor_leaves_out_nothing() -> None:
    """An empty session login names no actor, so no change is left out, not even one GitHub
    reports with an empty login."""
    closed = next(e for e in EVENTS if e["event"] == "closed" and "pull_request" not in e["issue"])
    nameless = {**closed, "actor": {"login": ""}, "created_at": "2026-10-02T01:00:00Z"}
    store, _ = recorded_store({"issues/events": [nameless]})
    changes = store.changes_since(datetime(2026, 10, 1, tzinfo=UTC), except_actor="")
    assert [(change.number, change.actor) for change in changes] == [
        (closed["issue"]["number"], "")
    ]


def test_changes_since_raises_when_the_events_outrun_the_page_cap(
    github_api: GitHubApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A chain of linked pages that never reaches back past the cutoff stops at the session's
    page cap, raising rather than taking the listing as whole."""
    referenced = next(event for event in EVENTS if event["event"] == "referenced")
    start = datetime(2026, 10, 3, tzinfo=UTC)
    full_page = [event_at(referenced, start - timedelta(minutes=n)) for n in range(100)]
    monkeypatch.setattr("devops_cli.github.session.DEFAULT_GH_MAX_PAGINATED_PAGES", 2)
    pages = [EVENTS_LISTING, *(f"{EVENTS_LISTING}&page={n}" for n in (2, 3))]
    for page, following in itertools.pairwise(pages):
        github_api.route("GET", page, github_json(full_page, headers=next_page(following)))
    store, _ = over_github()
    with pytest.raises(GitHubUnreadError, match="runs past 2 pages"):
        store.changes_since(datetime(2026, 10, 1, tzinfo=UTC))
    assert len(github_api.sent) == 2


# ── The factory ───────────────────────────────────────────────────────────────


def test_the_factory_opens_the_github_adapter_without_reading(
    github_roadmap_factory: Callable[..., RoadmapStore],
) -> None:
    store = github_roadmap_factory(REPO)
    assert type(store) is GitHubRoadmapStore


def test_a_store_the_factory_opens_reads_its_listings_through_the_processs_session(
    github_roadmap_factory: Callable[..., RoadmapStore], github_api: GitHubApiFake
) -> None:
    """Every roadmap command opens the store through the factory, which passes no session: its
    REST listings go through the process's GitHub session, and none through the gh runner
    (#983)."""
    github_api.route("GET", f"/{LISTING_MILESTONES}", github_json(MILESTONES))

    def refuse(args: list[str], **_: Any) -> NoReturn:
        raise AssertionError(f"the listing went through gh: {args}")

    store = github_roadmap_factory(REPO, runner=refuse)
    titles = [milestone.title for milestone in store.milestones()]
    assert (titles[0], github_api.requested) == (
        "2026-10-29",
        [f"GET {API}/{LISTING_MILESTONES}"],
    )


# ── Issues and files (#739) ───────────────────────────────────────────────────


def test_create_issue_posts_its_title_body_and_labels() -> None:
    opened = {**OPEN_ISSUES[1], "number": 950, "title": "Bare-Metal OS Installers"}
    store, runner = recorded_store({"-X POST": opened})
    created = store.create_issue("Bare-Metal OS Installers", "Rejected.", labels=["type/feature"])
    assert (runner.writes, created.number) == (
        [
            [
                "api",
                "-X",
                "POST",
                f"repos/{REPO}/issues",
                "-f",
                "title=Bare-Metal OS Installers",
                "-f",
                "body=Rejected.",
                "-f",
                "labels[]=type/feature",
            ]
        ],
        950,
    )


def test_issues_read_every_state_and_drop_pull_requests() -> None:
    store, runner = recorded_store({"issues?state=all": ISSUES_IN_MILESTONE + OPEN_ISSUES})
    numbers = [issue.number for issue in store.issues()]
    assert (
        918 in numbers,
        len(numbers) < len(ISSUES_IN_MILESTONE + OPEN_ISSUES),
        runner.calls[0][0],
    ) == (
        False,
        True,
        [f"{API}/repos/{REPO}/issues?state=all&per_page=100"],
    )


def test_repository_file_reads_raw_contents_at_the_ref() -> None:
    store, runner = recorded_store({"contents/": "- name: type/bug\n"})
    texts = (
        store.repository_file(".github/labels.yml", ref="feat/topic"),
        store.repository_file(".github/labels.yml"),
    )
    assert (texts, [args for args, _ in runner.calls]) == (
        ("- name: type/bug\n", "- name: type/bug\n"),
        [
            [
                "api",
                "-H",
                "Accept: application/vnd.github.raw+json",
                f"repos/{REPO}/contents/.github/labels.yml?ref=feat%2Ftopic",
            ],
            [
                "api",
                "-H",
                "Accept: application/vnd.github.raw+json",
                f"repos/{REPO}/contents/.github/labels.yml",
            ],
        ],
    )


def test_a_missing_file_raises_not_found_and_another_failure_raises_as_a_failed_read() -> None:
    missing, _ = recorded_store({"contents/": (1, "gh: Not Found (HTTP 404)")})
    broken, _ = recorded_store({"contents/": (1, "gh: Server Error (HTTP 502)")})
    with pytest.raises(GitHubFileNotFoundError, match=r"has no \.github/labels\.yml at main"):
        missing.repository_file(".github/labels.yml", ref="main")
    with pytest.raises(
        GitHubOperationError, match=r"Could not read \.github/labels\.yml"
    ) as failed:
        broken.repository_file(".github/labels.yml", ref="main")
    assert type(failed.value) is GitHubOperationError


# ── Comments ──────────────────────────────────────────────────────────────────


def test_comments_on_reads_every_comment_of_the_issue_oldest_first_with_its_time() -> None:
    store, runner = recorded_store({"issues/844/comments": recorded("issue-844-comments.json")})
    (comment,) = store.comments_on(844)
    assert (
        comment.body.startswith("**Placement (2026-10-02):** moved from v0.2.28"),
        comment.created_at,
        runner.calls[0][0],
    ) == (
        True,
        datetime(2026, 10, 2, 3, 26, 48, tzinfo=UTC),
        [f"{API}/repos/{REPO}/issues/844/comments?per_page=100"],
    )


def test_path_changed_at_reads_the_newest_commit_of_a_path_once_for_the_stores_life() -> None:
    """The newest commit on the default branch that changed a path, one commit a page, as the
    commits API lists them newest first; a path no commit changed has no time, and each path is
    read once for the store's life (#2005)."""
    newest = {"sha": "0a2bfe1f", "commit": {"committer": {"date": "2026-10-24T06:06:57Z"}}}
    store, runner = recorded_store({"path=src%2Fapp.py": [newest], "path=src%2Fgone.py": []})
    times = [store.path_changed_at(path) for path in ("src/app.py", "src/app.py", "src/gone.py")]
    assert (times, [args for args, _ in runner.calls]) == (
        [datetime(2026, 10, 24, 6, 6, 57, tzinfo=UTC)] * 2 + [None],
        [
            ["api", f"repos/{REPO}/commits?path=src%2Fapp.py&per_page=1"],
            ["api", f"repos/{REPO}/commits?path=src%2Fgone.py&per_page=1"],
        ],
    )


def test_a_failed_read_of_the_commits_of_a_path_raises() -> None:
    store, _ = recorded_store({"path=": (1, "gh: Server Error (HTTP 502)")})
    with pytest.raises(GitHubOperationError, match=r"Could not read the commits of src/app\.py"):
        store.path_changed_at("src/app.py")


def test_comment_posts_one_comment() -> None:
    store, runner = recorded_store({"-X POST": {}})
    store.comment(740, "Status set to Ready.")
    assert runner.writes == [
        [
            "api",
            "-X",
            "POST",
            f"repos/{REPO}/issues/740/comments",
            "-f",
            "body=Status set to Ready.",
        ]
    ]


def test_a_close_reads_the_issue_then_comments_then_patches_its_state_and_reason() -> None:
    """The read refuses a pull request or a closed issue before any write; the comment comes
    before the close, so a failed close leaves the evidence (#1658)."""
    closed = issue_payload(740, state="closed", state_reason="not_planned")
    store, runner = recorded_store(
        {"-X POST": {}, "-X PATCH": closed, "issues/740": issue_payload(740)}
    )
    store.close(740, CloseReason.NOT_PLANNED, comment="Superseded by #2399.")
    issue = f"repos/{REPO}/issues/740"
    assert [(args, kwargs.get("input")) for args, kwargs in runner.calls] == [
        (["api", issue], None),
        (["api", "-X", "POST", f"{issue}/comments", "-f", "body=Superseded by #2399."], None),
        (
            ["api", "-X", "PATCH", issue, "--input", "-"],
            json.dumps({"state": "closed", "state_reason": "not_planned"}),
        ),
    ]


def test_a_refused_close_after_its_comment_says_the_comment_is_on_the_open_issue() -> None:
    store, _ = recorded_store(
        {
            "-X POST": {},
            "-X PATCH": (1, "gh: Validation Failed (HTTP 422)"),
            "issues/740": issue_payload(740),
        }
    )
    with pytest.raises(GitHubOperationError, match=r"comment is on #740.*still open"):
        store.close(740, CloseReason.NOT_PLANNED, comment="Superseded.")


# ── What intake reads and writes (#742) ───────────────────────────────────────


def issue_payload(number: int, **changes: Any) -> dict[str, Any]:
    """The recorded open issue #917 as issue `number`, with its node id."""
    return {**OPEN_ISSUES[1], "number": number, "node_id": f"I_kw{number}", **changes}


def _timeline(nodes: list[dict[str, Any]], total: int | None = None) -> dict[str, Any]:
    connection = {"nodes": nodes, "totalCount": len(nodes) if total is None else total}
    return {"data": {"repository": {"issue": {"timelineItems": connection}}}}


def test_closures_read_the_timelines_closes_and_reopens_oldest_first() -> None:
    nodes: list[dict[str, Any]] = [
        {
            "__typename": "ClosedEvent",
            "createdAt": "2026-10-01T10:00:00Z",
            "stateReason": "DUPLICATE",
            "duplicateOf": {"number": 742},
        },
        {"__typename": "ReopenedEvent", "createdAt": "2026-10-01T11:00:00Z"},
    ]
    store, runner = recorded_store({"timelineItems": _timeline(nodes)})
    closures = store.closures(950)
    assert (
        [(c.kind, c.at.hour, c.reason, c.duplicate_of) for c in closures],
        runner.calls[0][0][-2:],
    ) == (
        [(ChangeKind.CLOSED, 10, "duplicate", 742), (ChangeKind.REOPENED, 11, None, None)],
        ["-F", "number=950"],
    )


def test_closures_past_the_connection_limit_raise() -> None:
    store, _ = recorded_store({"timelineItems": _timeline([], total=101)})
    with pytest.raises(GitHubOperationError, match="Read 0 of 101"):
        store.closures(950)


def test_label_issue_posts_one_label_and_keeps_the_others() -> None:
    store, runner = recorded_store({"-X POST": []})
    store.label_issue(950, "type/bug")
    assert runner.writes == [
        ["api", "-X", "POST", f"repos/{REPO}/issues/950/labels", "-f", "labels[]=type/bug"]
    ]


@pytest.mark.parametrize(
    ("kind", "value", "reply", "endpoint", "holds"),
    [
        (
            "advisory",
            "GHSA-abcd-efgh-ijkl",
            {"ghsa_id": "x"},
            "advisories/GHSA-abcd-efgh-ijkl",
            True,
        ),
        ("advisory", "GHSA-abcd-efgh-ijkl", (1, "gh: Not Found (HTTP 404)"), "advisories/", False),
        ("failed_run", "123", {"conclusion": "failure"}, f"repos/{REPO}/actions/runs/123", True),
        ("failed_run", "123", {"conclusion": "success"}, f"repos/{REPO}/actions/runs/123", False),
        ("regression_commit", "abc1234", {"sha": "abc1234"}, f"repos/{REPO}/commits/abc1234", True),
        ("regression_commit", "abc1234", (1, "HTTP 422: No commit found"), "commits/", False),
    ],
)
def test_evidence_holds_reads_the_advisory_run_or_commit(
    kind: str, value: str, reply: Any, endpoint: str, holds: bool
) -> None:
    store, runner = recorded_store({"api ": reply})
    found = store.evidence_holds(Evidence(kind=EvidenceKind(kind), value=value))
    assert (found, endpoint in runner.calls[0][0][-1]) == (holds, True)


def test_evidence_with_a_path_in_its_value_never_leaves_its_endpoint() -> None:
    store, runner = recorded_store({"api ": {"sha": "x"}})
    store.evidence_holds(Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="../pulls/1"))
    assert runner.calls[0][0][-1] == f"repos/{REPO}/commits/..%2Fpulls%2F1"


def test_issue_records_and_milestones_carry_author_and_close_times() -> None:
    closed = {**MILESTONES[0], "state": "closed", "closed_at": "2026-10-03T20:37:25Z"}
    store, _ = recorded_store(
        {
            "milestones?state=all": [closed],
            "issues?state=all": [
                issue_payload(
                    950,
                    author_association="COLLABORATOR",
                    created_at="2026-10-04T01:00:00Z",
                    updated_at="2026-10-04T02:30:00Z",
                    closed_at=None,
                )
            ],
        }
    )
    (issue,) = store.issues()
    (milestone,) = store.milestones()
    assert (
        issue.author_association,
        issue.created_at,
        issue.updated_at,
        milestone.closed_at,
    ) == (
        "COLLABORATOR",
        datetime(2026, 10, 4, 1, tzinfo=UTC),
        datetime(2026, 10, 4, 2, 30, tzinfo=UTC),
        datetime(2026, 10, 3, 20, 37, 25, tzinfo=UTC),
    )


def test_the_visibility_read_and_the_issue_write_send_their_arguments() -> None:
    owner, name = REPO.split("/", 1)
    assert (
        issue_edit_args(REPO, 42),
        json.loads(issue_edit(labels=["status/new"], body="Text")),
        json.loads(issue_edit(body="Text")),
        is_private_args(REPO),
    ) == (
        ["api", "-X", "PATCH", f"repos/{REPO}/issues/42", "--input", "-"],
        {"labels": ["status/new"], "body": "Text"},
        {"body": "Text"},
        [
            "api",
            "graphql",
            "-f",
            "query=query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { isPrivate } }",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
        ],
    )


def test_repository_is_private_github_store() -> None:
    store, _ = recorded_store({"isPrivate": {"data": {"repository": {"isPrivate": True}}}})
    assert store.repository_is_private() is True


def test_repository_facts_read_the_repository_and_its_latest_release() -> None:
    """One REST read of the repository and one of its latest release, with the license, the last
    push and the star count (#2650)."""
    repository = {
        "full_name": "example/tool",
        "html_url": "https://github.com/example/tool",
        "license": {"spdx_id": "MIT"},
        "archived": False,
        "pushed_at": "2026-10-29T15:04:03Z",
        "stargazers_count": 7,
    }
    release = {"tag_name": "v2.0.0", "published_at": "2026-10-28T00:55:47Z"}
    store, runner = recorded_store({"/releases/latest": release, "repos/example/tool": repository})
    assert (store.repository_facts("example/tool"), [args for args, _ in runner.calls]) == (
        RepositoryFacts(
            full_name="example/tool",
            url="https://github.com/example/tool",
            license="MIT",
            pushed_at=datetime(2026, 10, 29, 15, 4, 3, tzinfo=UTC),
            stars=7,
            latest_release="v2.0.0",
            released_at=datetime(2026, 10, 28, 0, 55, 47, tzinfo=UTC),
        ),
        [["api", "repos/example/tool"], ["api", "repos/example/tool/releases/latest"]],
    )


def test_repository_facts_of_a_repository_with_no_release_or_license() -> None:
    repository = {
        "full_name": "example/tool",
        "html_url": "https://github.com/example/tool",
        "license": None,
        "archived": True,
        "pushed_at": None,
        "stargazers_count": 0,
    }
    gone = (1, "gh: Not Found (HTTP 404)")
    store, _ = recorded_store({"/releases/latest": gone, "repos/example/tool": repository})
    facts = store.repository_facts("example/tool")
    assert facts is not None
    assert (
        facts.license,
        facts.archived,
        facts.pushed_at,
        facts.latest_release,
    ) == (None, True, None, None)


def test_repository_facts_of_a_missing_repository_are_none_and_a_failed_read_raises() -> None:
    missing, _ = recorded_store({"repos/example/none": (1, "gh: Not Found (HTTP 404)")})
    broken, _ = recorded_store({"repos/example/tool": (1, "gh: Server Error (HTTP 502)")})
    assert missing.repository_facts("example/none") is None
    with pytest.raises(GitHubOperationError, match=r"Could not read the repository example/tool"):
        broken.repository_facts("example/tool")


@pytest.mark.parametrize("name", ["scanner", "a/b/c", "../user", "example/..", "a b/c"])
def test_repository_facts_refuses_a_name_that_is_no_repository_name_before_any_request(
    name: str,
) -> None:
    store, runner = recorded_store({})
    with pytest.raises(GitHubOperationError, match="is not a repository name"):
        store.repository_facts(name)
    assert runner.calls == []
