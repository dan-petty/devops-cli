"""GitHub roadmap store over a stub runner that answers with recorded `gh` output.

The recorded listings under `tests/fixtures/roadmap/` come from dan-petty/devops-cli and its
board (project 2), trimmed to the keys the store reads. No case runs `gh` or opens a socket.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from packaging.version import Version

from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.roadmap.store import ChangeKind, GitHubState, Item, ItemField, RoadmapStore

FIXTURES = Path(__file__).parent / "fixtures" / "roadmap"
REPO = "dan-petty/devops-cli"
ISSUE_URL = f"https://github.com/{REPO}/issues"


def recorded(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


MILESTONES = recorded("milestones.json")
BOARD = recorded("project-item-list.json")
FIELDS = recorded("project-field-list.json")
ISSUES_IN_RELEASE = recorded("issues-milestone-43.json")
OPEN_ISSUES = recorded("issues-open.json")
EVENTS = recorded("issue-events.json")

LISTING_MILESTONES = f"repos/{REPO}/milestones?state=all&per_page=100"
LISTING_IN_RELEASE = f"repos/{REPO}/issues?milestone=43&state=all&per_page=100"


def fields_with_job_record() -> dict[str, Any]:
    listing: dict[str, Any] = deepcopy(FIELDS)
    listing["fields"].append(
        {"id": "PVTF_jobrecord", "name": "Job record", "type": "ProjectV2Field"}
    )
    listing["totalCount"] += 1
    return listing


def created_milestone(number: int, title: str, **changes: Any) -> dict[str, Any]:
    """The recorded v0.2.25 milestone, as GitHub would return it after a write."""
    milestone = next(m for m in MILESTONES if m["title"] == "v0.2.25")
    return {**milestone, "number": number, "title": title, **changes}


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
        return [
            args for args, _ in self.calls if {"POST", "PATCH", "item-edit", "item-add"} & set(args)
        ]


def board_store(replies: dict[str, Any]) -> tuple[GitHubRoadmapStore, RecordedGh]:
    runner = RecordedGh(replies)
    return GitHubRoadmapStore(REPO, board_owner="dan-petty", board_number=2, runner=runner), runner


def board_item(number: int, **fields: Any) -> Item:
    return Item(number=number, title=f"#{number}", url=f"{ISSUE_URL}/{number}", **fields)


# ── Releases ──────────────────────────────────────────────────────────────────


def test_a_release_is_the_same_milestone_with_or_without_its_v() -> None:
    store, _ = board_store({"milestones?state=all": MILESTONES})
    found = (store.release("0.2.25"), store.release("v0.2.25"))
    assert [release.number if release else None for release in found] == [43, 43]


def test_releases_sort_recorded_milestones_by_version() -> None:
    store, _ = board_store({"milestones?state=all": MILESTONES})
    titles = [release.title for release in store.releases()]
    assert (
        titles.index("v0.2.10") - titles.index("v0.2.9"),
        titles == sorted(titles, key=Version),
        len(titles),
    ) == (1, True, len(MILESTONES))


def test_a_milestone_that_is_not_a_version_is_skipped_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, _ = board_store(
        {"milestones?state=all": [*MILESTONES, {**MILESTONES[0], "title": "Someday"}]}
    )
    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.github_store"):
        titles = [release.title for release in store.releases()]
    assert ("Someday" in titles, len(titles), "'Someday'" in caplog.text) == (
        False,
        len(MILESTONES),
        True,
    )


def test_create_release_posts_title_description_due_date_and_state() -> None:
    store, runner = board_store(
        {
            "milestones?state=all": MILESTONES,
            "-X POST": created_milestone(47, "v0.3.6", due_on="2026-11-01T07:00:00Z"),
        }
    )
    created = store.create_release("0.3.6", description="Next", due_on=date(2026, 11, 1))
    assert (runner.writes, created.number, created.due_on) == (
        [
            [
                "api",
                "-X",
                "POST",
                f"repos/{REPO}/milestones",
                "-f",
                "title=v0.3.6",
                "-f",
                "description=Next",
                "-f",
                "due_on=2026-11-01T00:00:00Z",
                "-f",
                "state=open",
            ]
        ],
        47,
        date(2026, 11, 1),
    )


def test_creating_a_version_that_already_exists_raises_without_writing() -> None:
    store, runner = board_store({"milestones?state=all": MILESTONES})
    with pytest.raises(GitHubOperationError, match="already exists"):
        store.create_release("0.2.25")
    assert runner.writes == []


def test_edit_release_sends_only_the_fields_it_is_given() -> None:
    store, runner = board_store(
        {"milestones?state=all": MILESTONES, "-X PATCH": created_milestone(43, "v0.2.26")}
    )
    store.edit_release("v0.2.25", title="0.2.26b1", due_on=date(2026, 12, 24))
    assert runner.writes == [
        [
            "api",
            "-X",
            "PATCH",
            f"repos/{REPO}/milestones/43",
            "-f",
            "title=v0.2.26b1",
            "-f",
            "due_on=2026-12-24T00:00:00Z",
        ]
    ]


def test_an_edit_that_names_no_state_sends_no_state() -> None:
    store, runner = board_store(
        {"milestones?state=all": MILESTONES, "-X PATCH": created_milestone(43, "v0.2.25")}
    )
    edited = store.edit_release("0.2.25", description="new text")
    assert (runner.writes, edited.state) == (
        [["api", "-X", "PATCH", f"repos/{REPO}/milestones/43", "-f", "description=new text"]],
        GitHubState.OPEN,
    )


def test_an_edit_with_nothing_to_change_writes_nothing() -> None:
    store, runner = board_store({"milestones?state=all": MILESTONES})
    assert (store.edit_release("0.2.25").number, runner.writes) == (43, [])


def test_close_release_patches_only_its_state() -> None:
    store, runner = board_store(
        {
            "milestones?state=all": MILESTONES,
            "-X PATCH": created_milestone(43, "v0.2.25", state="closed"),
        }
    )
    closed = store.close_release("v0.2.25")
    assert (runner.writes, closed.state) == (
        [["api", "-X", "PATCH", f"repos/{REPO}/milestones/43", "-f", "state=closed"]],
        GitHubState.CLOSED,
    )


# ── Items and Candidates ──────────────────────────────────────────────────────


def on_board(*numbers: int) -> dict[str, Any]:
    """The recorded board, with an issue of this repository added for each number."""
    board: dict[str, Any] = deepcopy(BOARD)
    for number in numbers:
        board_entry = deepcopy(board["items"][0])
        board_entry["content"].update(number=number, url=f"{ISSUE_URL}/{number}")
        board["items"].append(board_entry)
    board["totalCount"] = len(board["items"])
    return board


def test_a_board_of_an_issue_a_pull_request_a_draft_and_a_foreign_issue_yields_one_item() -> None:
    store, _ = board_store(
        {
            "item-list": BOARD,
            "issues?state=all": ISSUES_IN_RELEASE + OPEN_ISSUES,
            "issues/737": ISSUES_IN_RELEASE[2],
        }
    )
    items = store.items()
    assert (
        [item.number for item in items],
        [content["content"]["type"] for content in BOARD["items"]],
        store.item(246),
        store.item(540),
    ) == ([737], ["Issue", "PullRequest", "DraftIssue", "Issue"], None, None)


def test_items_in_a_release_include_a_closed_issue_with_state_and_release_from_rest() -> None:
    store, runner = board_store(
        {
            "milestones?state=all": MILESTONES,
            "item-list": BOARD,
            "issues?milestone=43": ISSUES_IN_RELEASE,
        }
    )
    items = store.items(release="v0.2.25")
    assert (
        [
            (item.number, item.state, item.state_reason, item.release, item.status, item.priority)
            for item in items
        ],
        [args[2] for args, _ in runner.calls if "--paginate" in args],
    ) == (
        [(737, GitHubState.CLOSED, "completed", "v0.2.25", "Done", "P1-High")],
        [LISTING_MILESTONES, LISTING_IN_RELEASE],
    )


def test_items_in_an_unknown_release_are_none() -> None:
    store, _ = board_store({"milestones?state=all": MILESTONES, "item-list": BOARD})
    assert store.items(release="9.9.9") == []


def test_backlog_reads_the_open_issues_in_no_milestone() -> None:
    open_on_board = {**ISSUES_IN_RELEASE[1], "milestone": None}
    store, runner = board_store(
        {"item-list": on_board(739), "issues?milestone=none": [open_on_board]}
    )
    assert ([item.number for item in store.backlog()], runner.calls[-1][0][2]) == (
        [739],
        f"repos/{REPO}/issues?milestone=none&state=open&per_page=100",
    )


def test_candidates_drop_a_pull_request_and_an_issue_already_on_the_board() -> None:
    # The recorded pull request #918 had merged; it is reopened here, so only its
    # `pull_request` key can keep it out.
    listing = deepcopy(OPEN_ISSUES)
    listing[0]["state"] = "open"
    store, _ = board_store({"item-list": on_board(917), "issues?state=open": listing})
    assert [(c.number, c.labels) for c in store.candidates()] == [
        (916, ("type/bug", "scope/security", "priority/p3-low"))
    ]


def test_items_carry_the_job_record_the_board_holds() -> None:
    board = on_board(739, 768)
    board["items"][-2]["job record"] = '{"Priority": "P1-High", "Release": "v0.2.25"}'
    board["items"][-1]["job record"] = "not json"
    store, _ = board_store({"item-list": board, "issues?state=all": ISSUES_IN_RELEASE})
    assert [(item.number, item.job_record) for item in store.items()] == [
        (737, {}),
        (739, {ItemField.PRIORITY: "P1-High", ItemField.RELEASE: "v0.2.25"}),
        (768, {}),
    ]


# ── Item writes ───────────────────────────────────────────────────────────────


def test_a_value_that_is_not_a_board_option_raises_without_writing() -> None:
    store, runner = board_store({"field-list": fields_with_job_record(), "item-list": BOARD})
    with pytest.raises(GitHubOperationError, match="not a Priority option"):
        store.set_field(board_item(737), ItemField.PRIORITY, "P9-Someday")
    assert runner.writes == []


def test_setting_priority_edits_the_field_then_the_job_record() -> None:
    # The Item was read before its Status was recorded; the record merges into the board's.
    board = on_board()
    board["items"][0]["job record"] = '{"Status": "Done"}'
    store, runner = board_store(
        {"field-list": fields_with_job_record(), "item-list": board, "item-edit": ""}
    )
    store.set_field(board_item(737, status="Done"), ItemField.PRIORITY, "P2-Medium")
    edit = ["project", "item-edit", "2", "--owner", "dan-petty", "--url", f"{ISSUE_URL}/737"]
    record = runner.writes[-1][-1]
    assert (runner.writes, json.loads(record)) == (
        [
            [*edit, "--field", "Priority", "--value", "P2-Medium"],
            [*edit, "--field", "Job record", "--text", record],
        ],
        {"Priority": "P2-Medium", "Status": "Done"},
    )


def test_two_writes_from_one_read_keep_both_fields_in_the_job_record() -> None:
    board = on_board()

    def edit_board(args: list[str]) -> str:
        if "Job record" in args:
            board["items"][0]["job record"] = args[-1]
        return ""

    store, runner = board_store(
        {
            "field-list": fields_with_job_record(),
            "item-list": board,
            "item-edit": edit_board,
            f"api repos/{REPO}/issues/737": ISSUES_IN_RELEASE[2],
        }
    )
    item = store.item(737)
    assert item is not None
    store.set_field(item, ItemField.PRIORITY, "P2-Medium")
    store.set_field(item, ItemField.STATUS, "Ready")
    assert [json.loads(args[-1]) for args in runner.writes if "Job record" in args] == [
        {"Priority": "P2-Medium"},
        {"Priority": "P2-Medium", "Status": "Ready"},
    ]


def test_writing_an_item_that_is_not_on_the_board_raises_without_writing() -> None:
    store, runner = board_store({"field-list": fields_with_job_record(), "item-list": BOARD})
    with pytest.raises(GitHubOperationError, match="#739 is not on the board"):
        store.set_field(board_item(739), ItemField.STATUS, "Ready")
    assert runner.writes == []


def test_clearing_a_field_sends_clear_and_records_null() -> None:
    store, runner = board_store(
        {"field-list": fields_with_job_record(), "item-list": BOARD, "item-edit": ""}
    )
    store.set_field(board_item(737), ItemField.EFFORT, None)
    assert [args[8:] for args in runner.writes] == [
        ["Effort", "--clear"],
        ["Job record", "--text", '{"Effort": null}'],
    ]


def test_a_board_without_a_job_record_field_raises_before_any_write() -> None:
    store, runner = board_store({"field-list": FIELDS})
    with pytest.raises(GitHubOperationError, match="Job record"):
        store.set_field(board_item(737), ItemField.PRIORITY, "P2-Medium")
    assert (runner.writes, [args[:2] for args, _ in runner.calls]) == (
        [],
        [["project", "field-list"]],
    )


def test_placing_an_item_in_a_release_sets_its_milestone_then_records_it() -> None:
    store, runner = board_store(
        {
            "field-list": fields_with_job_record(),
            "item-list": on_board(739),
            "milestones?state=all": MILESTONES,
            "-X PATCH": ISSUES_IN_RELEASE[1],
            "item-edit": "",
        }
    )
    store.set_field(board_item(739), ItemField.RELEASE, "0.2.25")
    store.set_field(board_item(739), ItemField.RELEASE, None)
    assert [args[3:] if args[0] == "api" else args[8:] for args in runner.writes] == [
        [f"repos/{REPO}/issues/739", "-F", "milestone=43"],
        ["Job record", "--text", '{"Release": "v0.2.25"}'],
        [f"repos/{REPO}/issues/739", "-F", "milestone=null"],
        ["Job record", "--text", '{"Release": null}'],
    ]


def test_add_item_adds_the_issue_by_its_url() -> None:
    store, runner = board_store({"issues/917": OPEN_ISSUES[1], "item-add": ""})
    store.add_item(917)
    assert runner.writes == [
        ["project", "item-add", "2", "--owner", "dan-petty", "--url", f"{ISSUE_URL}/917"]
    ]


def test_add_item_refuses_a_pull_request() -> None:
    store, runner = board_store({"issues/918": OPEN_ISSUES[0]})
    with pytest.raises(GitHubOperationError, match="pull request"):
        store.add_item(918)
    assert runner.writes == []


def test_item_reads_and_writes_raise_without_a_board() -> None:
    runner = RecordedGh({})
    store = GitHubRoadmapStore(REPO, runner=runner)
    with pytest.raises(GitHubOperationError, match="No board"):
        store.items()
    with pytest.raises(GitHubOperationError, match="No board"):
        store.add_item(917)
    assert runner.calls == []


# ── Failed reads ──────────────────────────────────────────────────────────────


def test_a_non_zero_exit_raises_and_names_the_read() -> None:
    store, _ = board_store({"milestones?state=all": (1, "HTTP 502: Bad Gateway")})
    with pytest.raises(GitHubOperationError, match="Could not read milestones"):
        store.releases()


def test_a_rate_limited_read_raises_rate_limit_error() -> None:
    store, _ = board_store({"milestones?state=all": (1, "API rate limit exceeded for user ID 1.")})
    with pytest.raises(GitHubRateLimitError):
        store.releases()


def test_malformed_json_raises() -> None:
    store, _ = board_store({"milestones?state=all": '[{"number": 1, "title": '})
    with pytest.raises(GitHubOperationError, match="malformed milestones"):
        store.releases()


def test_an_error_object_where_a_listing_belongs_raises() -> None:
    store, _ = board_store({"issues?state=open": {"message": "Not Found"}, "item-list": BOARD})
    with pytest.raises(GitHubOperationError, match="malformed issues"):
        store.candidates()


def test_a_board_listing_with_fewer_items_than_its_total_raises() -> None:
    store, _ = board_store({"item-list": {**BOARD, "totalCount": 676}})
    with pytest.raises(GitHubOperationError, match="Read 4 of 676"):
        store.backlog()


def test_a_failed_write_raises() -> None:
    store, _ = board_store(
        {
            "field-list": fields_with_job_record(),
            "item-list": BOARD,
            "item-edit": (1, "GraphQL: Could not resolve"),
        }
    )
    with pytest.raises(GitHubOperationError, match="Could not set Status on #737"):
        store.set_field(board_item(737), ItemField.STATUS, "Ready")


# ── Paging and caching ────────────────────────────────────────────────────────


def test_every_rest_listing_follows_api_paginate_and_asks_for_full_pages() -> None:
    store, runner = board_store(
        {
            "milestones?state=all": MILESTONES,
            "item-list": BOARD,
            "issues?milestone=43": ISSUES_IN_RELEASE,
            "issues?milestone=none": [],
            "issues?state=": OPEN_ISSUES,
        }
    )
    store.items(release="0.2.25")
    store.items()
    store.backlog()
    store.candidates()
    listings = [args for args, _ in runner.calls if args[0] == "api"]
    assert (
        [args[:2] for args in listings],
        [parse_qs(urlsplit(args[2]).query)["per_page"] for args in listings],
    ) == ([["api", "--paginate"]] * 5, [["100"]] * 5)


def test_every_read_passes_use_cache_false() -> None:
    store, runner = board_store(
        {
            "milestones?state=all": MILESTONES,
            "item-list": BOARD,
            "field-list": FIELDS,
            "issues?milestone=43": ISSUES_IN_RELEASE,
            "issues/737": ISSUES_IN_RELEASE[2],
            "issues?state=open": OPEN_ISSUES,
            "issues/events": EVENTS,
        }
    )
    store.items(release="0.2.25")
    store.item(737)
    store.candidates()
    store.changes_since(datetime(2026, 10, 1, tzinfo=UTC))
    with pytest.raises(GitHubOperationError, match="Job record"):
        store.set_field(board_item(737), ItemField.STATUS, "Ready")
    assert ([kwargs["use_cache"] for _, kwargs in runner.calls], len(runner.calls)) == (
        [False] * 9,
        9,
    )


def event_at(template: dict[str, Any], moment: datetime) -> dict[str, Any]:
    return {**template, "created_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ")}


def test_changes_since_pages_newest_first_and_stops_at_the_first_older_event() -> None:
    referenced = next(event for event in EVENTS if event["event"] == "referenced")
    start = datetime(2026, 10, 3, tzinfo=UTC)
    newer_page = [event_at(referenced, start - timedelta(minutes=n)) for n in range(100)]
    oldest_recorded = datetime.fromisoformat(EVENTS[-1]["created_at"])
    older_padding = [
        event_at(referenced, oldest_recorded - timedelta(minutes=n + 1)) for n in range(90)
    ]
    store, runner = board_store(
        {
            "&page=1": newer_page,
            "&page=2": EVENTS + older_padding,
            "&page=3": (1, "page 3 must not be read"),
        }
    )
    changes = store.changes_since(datetime(2026, 10, 1, 22, 0, tzinfo=UTC))
    assert (
        [args for args, _ in runner.calls],
        [(change.kind, change.number, change.at.isoformat()) for change in changes],
    ) == (
        [
            ["api", f"repos/{REPO}/issues/events?per_page=100&page=1"],
            ["api", f"repos/{REPO}/issues/events?per_page=100&page=2"],
        ],
        [
            (ChangeKind.JOINED_RELEASE, 912, "2026-10-01T22:17:49+00:00"),
            (ChangeKind.CLOSED, 299, "2026-10-01T22:39:06+00:00"),
            (ChangeKind.LABELED, 917, "2026-10-01T22:39:11+00:00"),
        ],
    )


def test_changes_since_keeps_issue_release_label_and_state_events_only() -> None:
    closed = next(e for e in EVENTS if e["event"] == "closed" and "pull_request" not in e["issue"])
    reopened = {**closed, "event": "reopened", "created_at": "2026-10-02T01:00:00Z"}
    store, _ = board_store({"issues/events": [reopened, *EVENTS]})
    changes = store.changes_since(datetime(2026, 10, 1))
    assert [
        (change.kind, change.number, change.actor, change.release or change.label)
        for change in changes
    ] == [
        (ChangeKind.LEFT_RELEASE, 829, "dan-petty", "v0.2.28"),
        (ChangeKind.UNLABELED, 829, "dan-petty", "priority/p1-high"),
        (ChangeKind.JOINED_RELEASE, 912, "dan-petty", "v0.2.24"),
        (ChangeKind.CLOSED, 299, "dan-petty", None),
        (ChangeKind.LABELED, 917, "dan-petty", "priority/p3-low"),
        (ChangeKind.REOPENED, 299, "dan-petty", None),
    ]


def test_changes_since_raises_when_the_events_outrun_the_page_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    referenced = next(event for event in EVENTS if event["event"] == "referenced")
    start = datetime(2026, 10, 3, tzinfo=UTC)
    full_page = [event_at(referenced, start - timedelta(minutes=n)) for n in range(100)]
    monkeypatch.setattr("devops_cli.roadmap.github_store.DEFAULT_GH_MAX_PAGINATED_PAGES", 2)
    store, runner = board_store({"issues/events": full_page})
    with pytest.raises(GitHubOperationError, match="run past 2 pages"):
        store.changes_since(datetime(2026, 10, 1, tzinfo=UTC))
    assert len(runner.calls) == 2


def test_the_factory_opens_the_github_adapter_without_reading(
    github_roadmap_factory: Callable[..., RoadmapStore],
) -> None:
    store = github_roadmap_factory(REPO, board_owner="dan-petty", board_number=2)
    assert type(store) is GitHubRoadmapStore
