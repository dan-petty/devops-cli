"""GitHub roadmap store over a stub runner that answers with recorded `gh` output.

The recorded listings under `tests/fixtures/roadmap/` come from dan-petty/devops-cli and its
board (project 2), trimmed to the keys the store reads. No case runs `gh` or opens a socket.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from packaging.version import Version

from devops_cli.config.constants import CONST_ROADMAP_RUN_RECORD_BODY
from devops_cli.exceptions.git import (
    GitHubFileNotFoundError,
    GitHubOperationError,
    GitHubRateLimitError,
)
from devops_cli.github.rate_limiter import GitHubRateLimiter, reset_github_rate_limiter
from devops_cli.roadmap.config import RoadmapConfig
from devops_cli.roadmap.github_store import (
    GitHubRoadmapStore,
    is_private_args,
    option_update_request,
    write_issue_body_args,
)
from devops_cli.roadmap.reprioritize import plan_reprioritization
from devops_cli.roadmap.store import (
    Card,
    CardKind,
    ChangeKind,
    CloseReason,
    Evidence,
    EvidenceKind,
    FieldOption,
    FieldSpec,
    GitHubState,
    IssueQuery,
    Item,
    ItemField,
    JobMark,
    PullRequestState,
    RoadmapStore,
)
from tests.roadmap_board_fake import BOARD_READ, BoardServer

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
        changing = {
            "POST",
            "PATCH",
            "DELETE",
            "item-edit",
            "item-add",
            "item-create",
            "item-delete",
            "field-delete",
            "create",
            "link",
            "--input",
        }
        return [args for args, _ in self.calls if changing & set(args)]

    def inputs(self) -> list[Any]:
        """The JSON each call sent on stdin, in call order."""
        return [json.loads(kwargs["input"]) for _, kwargs in self.calls if kwargs.get("input")]


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
        board_entry["id"] = f"PVTI_{number}"
        board_entry["content"].update(number=number, url=f"{ISSUE_URL}/{number}")
        board["items"].append(board_entry)
    board["totalCount"] = len(board["items"])
    return board


def test_a_board_of_an_issue_a_pull_request_a_draft_and_a_foreign_issue_yields_one_item() -> None:
    store, _ = board_store(
        {
            BOARD_READ: BoardServer(BOARD),
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
            BOARD_READ: BoardServer(BOARD),
            "issues?milestone=43": ISSUES_IN_RELEASE,
        }
    )
    items = store.items(release="v0.2.25")
    assert (
        [
            (item.number, item.state, item.state_reason, item.release, item.status, item.priority)
            for item in items
        ],
        [args[1] for args, _ in runner.calls if args[0] == "api" and args[1] != "graphql"],
    ) == (
        [(737, GitHubState.CLOSED, "completed", "v0.2.25", "Done", "P1-High")],
        [f"{LISTING_MILESTONES}&page=1", f"{LISTING_IN_RELEASE}&page=1"],
    )


def test_items_in_an_unknown_release_are_none() -> None:
    store, _ = board_store({"milestones?state=all": MILESTONES, BOARD_READ: BoardServer(BOARD)})
    assert store.items(release="9.9.9") == []


def test_backlog_reads_the_open_issues_in_no_milestone() -> None:
    open_on_board = {**ISSUES_IN_RELEASE[1], "milestone": None}
    store, runner = board_store(
        {BOARD_READ: BoardServer(on_board(739)), "issues?milestone=none": [open_on_board]}
    )
    assert ([item.number for item in store.backlog()], runner.calls[-1][0][1]) == (
        [739],
        f"repos/{REPO}/issues?milestone=none&state=open&per_page=100&page=1",
    )


def test_candidates_drop_a_pull_request_and_an_issue_already_on_the_board() -> None:
    # The recorded pull request #918 had merged; it is reopened here, so only its
    # `pull_request` key can keep it out.
    listing = deepcopy(OPEN_ISSUES)
    listing[0]["state"] = "open"
    store, _ = board_store({BOARD_READ: BoardServer(on_board(917)), "issues?state=open": listing})
    assert [(c.number, c.labels) for c in store.candidates()] == [
        (916, ("type/bug", "scope/security", "priority/p3-low"))
    ]


def test_items_carry_the_known_keys_of_the_job_record_the_board_holds() -> None:
    """A key this version doesn't know, such as one a newer version writes, is left out."""
    board = on_board(739, 768)
    board["items"][-2]["job record"] = '{"Priority": "P1-High", "Release": "v0.2.25"}'
    board["items"][-1]["job record"] = '{"Admitted": "v0.2.25", "NeedsSplit": "yes"}'
    store, _ = board_store({BOARD_READ: BoardServer(board), "issues?state=all": ISSUES_IN_RELEASE})
    assert [(item.number, item.job_record) for item in store.items()] == [
        (737, {}),
        (739, {ItemField.PRIORITY: "P1-High", ItemField.RELEASE: "v0.2.25"}),
        (768, {JobMark.ADMITTED: "v0.2.25"}),
    ]


@pytest.mark.parametrize(
    "record",
    ["not json", '["Admitted", "v0.2.25"]', '{"Admitted": 25}'],
    ids=["not-json", "not-an-object", "a-known-key-without-text"],
)
def test_a_job_record_that_cannot_be_decoded_fails_the_read_and_names_its_card(
    record: str,
) -> None:
    """Read as empty, the card would look as if no job had ever placed or admitted it."""
    board = on_board(768)
    board["items"][-1]["job record"] = record
    store, runner = board_store(
        {BOARD_READ: BoardServer(board), "issues?state=all": ISSUES_IN_RELEASE}
    )
    with pytest.raises(GitHubOperationError, match="job record of #768 is not a JSON object"):
        store.items()
    assert runner.writes == []


# ── Item writes ───────────────────────────────────────────────────────────────


def test_a_value_that_is_not_a_board_option_raises_without_writing() -> None:
    store, runner = board_store(
        {"field-list": fields_with_job_record(), BOARD_READ: BoardServer(BOARD)}
    )
    with pytest.raises(GitHubOperationError, match="not a Priority option"):
        store.set_field(board_item(737), ItemField.PRIORITY, "P9-Someday")
    assert runner.writes == []


def test_setting_priority_records_it_in_the_job_record_then_edits_the_field() -> None:
    # The Item was read before its Status was recorded; the record merges into the board's.
    board = on_board()
    board["items"][0]["job record"] = '{"Status": "Done"}'
    store, runner = board_store(
        {"field-list": fields_with_job_record(), BOARD_READ: BoardServer(board), "item-edit": ""}
    )
    store.set_field(board_item(737, status="Done"), ItemField.PRIORITY, "P2-Medium")
    edit = ["project", "item-edit", "2", "--owner", "dan-petty", "--url", f"{ISSUE_URL}/737"]
    record = runner.writes[0][-1]
    assert (runner.writes, json.loads(record)) == (
        [
            [*edit, "--field", "Job record", "--text", record],
            [*edit, "--field", "Priority", "--value", "P2-Medium"],
        ],
        {"Priority": "P2-Medium", "Status": "Done"},
    )


def test_a_field_write_sets_marks_in_the_write_that_records_its_value() -> None:
    """The record of the value and the marks go in one write, before the field: a job that
    stops after it finds both, and one that stops before it finds neither."""
    store, runner = board_store(
        {"field-list": fields_with_job_record(), BOARD_READ: BoardServer(BOARD), "item-edit": ""}
    )
    store.set_field(board_item(737), ItemField.STATUS, "Ready", marks={JobMark.PENDING: "{}"})
    assert [(args[8], args[9:]) for args in runner.writes] == [
        ("Job record", ["--text", '{"Pending": "{}", "Status": "Ready"}']),
        ("Status", ["--value", "Ready"]),
    ]


def test_two_writes_from_one_read_keep_both_fields_in_the_job_record() -> None:
    board = on_board()

    def edit_board(args: list[str]) -> str:
        if "Job record" in args:
            board["items"][0]["job record"] = args[-1]
        return ""

    store, runner = board_store(
        {
            "field-list": fields_with_job_record(),
            BOARD_READ: BoardServer(board),
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
    store, runner = board_store(
        {"field-list": fields_with_job_record(), BOARD_READ: BoardServer(BOARD)}
    )
    with pytest.raises(GitHubOperationError, match="#739 is not on the board"):
        store.set_field(board_item(739), ItemField.STATUS, "Ready")
    assert runner.writes == []


def test_clearing_a_field_sends_clear_and_records_null() -> None:
    store, runner = board_store(
        {"field-list": fields_with_job_record(), BOARD_READ: BoardServer(BOARD), "item-edit": ""}
    )
    store.set_field(board_item(737), ItemField.EFFORT, None)
    assert [args[8:] for args in runner.writes] == [
        ["Job record", "--text", '{"Effort": null}'],
        ["Effort", "--clear"],
    ]


def test_a_board_without_a_job_record_field_raises_before_any_write() -> None:
    store, runner = board_store({"field-list": FIELDS})
    with pytest.raises(GitHubOperationError, match="Job record"):
        store.set_field(board_item(737), ItemField.PRIORITY, "P2-Medium")
    assert (runner.writes, [args[:2] for args, _ in runner.calls]) == (
        [],
        [["project", "field-list"]],
    )


def test_placing_an_item_in_a_release_records_it_then_sets_its_milestone() -> None:
    store, runner = board_store(
        {
            "field-list": fields_with_job_record(),
            BOARD_READ: BoardServer(on_board(739)),
            "milestones?state=all": MILESTONES,
            "-X PATCH": ISSUES_IN_RELEASE[1],
            "item-edit": "",
        }
    )
    store.set_field(board_item(739), ItemField.RELEASE, "0.2.25")
    store.set_field(board_item(739), ItemField.RELEASE, None)
    assert [args[3:] if args[0] == "api" else args[8:] for args in runner.writes] == [
        ["Job record", "--text", '{"Release": "v0.2.25"}'],
        [f"repos/{REPO}/issues/739", "-F", "milestone=43"],
        ["Job record", "--text", '{"Release": null}'],
        [f"repos/{REPO}/issues/739", "-F", "milestone=null"],
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
    store, _ = board_store(
        {"issues?state=open": {"message": "Not Found"}, BOARD_READ: BoardServer(BOARD)}
    )
    with pytest.raises(GitHubOperationError, match="malformed issues"):
        store.candidates()


def test_a_board_listing_with_fewer_items_than_its_total_raises() -> None:
    store, _ = board_store({BOARD_READ: BoardServer({**BOARD, "totalCount": 676})})
    with pytest.raises(GitHubOperationError, match="Read 4 of 676"):
        store.backlog()


def test_a_failed_write_raises() -> None:
    """The job record goes first, so when its write fails the field is never written."""
    store, runner = board_store(
        {
            "field-list": fields_with_job_record(),
            BOARD_READ: BoardServer(BOARD),
            "item-edit": (1, "GraphQL: Could not resolve"),
        }
    )
    with pytest.raises(GitHubOperationError, match="Could not set Job record on #737"):
        store.set_field(board_item(737), ItemField.STATUS, "Ready")
    assert [args[8] for args in runner.writes] == ["Job record"]


# ── Paging and caching ────────────────────────────────────────────────────────


def test_every_rest_listing_is_read_a_full_page_at_a_time() -> None:
    """The adapter pages each listing itself, so it sees every page: `api --paginate` would
    end the listing at a page that is empty or not JSON as if it were the last."""
    store, runner = board_store(
        {
            "milestones?state=all": MILESTONES,
            BOARD_READ: BoardServer(BOARD),
            "issues?milestone=43": ISSUES_IN_RELEASE,
            "issues?milestone=none": [],
            "issues?state=": OPEN_ISSUES,
        }
    )
    store.items(release="0.2.25")
    store.items()
    store.backlog()
    store.candidates()
    listings = [args for args, _ in runner.calls if args[0] == "api" and args[1] != "graphql"]
    assert (
        [len(args) for args in listings],
        [_query(args, "per_page", "page") for args in listings],
    ) == ([2] * 5, [(["100"], ["1"])] * 5)


def _query(args: list[str], *names: str) -> tuple[list[str], ...]:
    """The values of `names` in the query of the endpoint a REST read names last."""
    query = parse_qs(urlsplit(args[-1]).query)
    return tuple(query.get(name, []) for name in names)


def _pages(full: Any, body: str, bad: int) -> Callable[[list[str]], Any]:
    """A listing whose pages before `bad` are full, and whose page `bad` is `body`."""

    def page(args: list[str]) -> Any:
        (number,) = _query(args, "page")[0]
        return body if int(number) == bad else [full] * 100

    return page


LISTINGS: list[tuple[str, Any, Callable[[GitHubRoadmapStore], object], str]] = [
    ("milestones?state=all", MILESTONES[0], lambda store: store.releases(), "milestones"),
    ("issues?state=all", OPEN_ISSUES[1], lambda store: store.issues(), "issues"),
    (
        "issues/844/events",
        recorded("issue-844-events.json")[0],
        lambda store: store.release_changes(844),
        "#844 events",
    ),
    (
        "issues/844/comments",
        recorded("issue-844-comments.json")[0],
        lambda store: store.comments_on(844),
        "#844 comments",
    ),
    (
        "dependencies/blocked_by",
        recorded("issue-743.json"),
        lambda store: store.dependencies(740),
        "#740 dependencies",
    ),
]


@pytest.mark.parametrize("bad", [1, 2], ids=["first-page", "later-page"])
@pytest.mark.parametrize(
    "body",
    ["<html>upstream</html>", "", '{"message": "Server Error"}'],
    ids=["html", "empty", "object"],
)
@pytest.mark.parametrize(
    ("key", "full", "read", "what"),
    LISTINGS,
    ids=["milestones", "issues", "events", "comments", "dependencies"],
)
def test_a_listing_page_that_is_not_a_json_list_raises_naming_the_read(
    key: str,
    full: Any,
    read: Callable[[GitHubRoadmapStore], object],
    what: str,
    body: str,
    bad: int,
) -> None:
    """The reviewers' replay: a page answered with exit 0 and a body that is not a JSON list,
    such as a proxy's HTML, read as the end of the listing, so a bad first page gave an empty
    listing and a bad later page a short one. Each raises now, naming the read, before any
    write."""
    store, runner = board_store({key: _pages(full, body, bad)})
    with pytest.raises(GitHubOperationError, match=f"malformed {what} \\(page {bad}\\)"):
        read(store)
    assert (
        [_query(args, "page")[0] for args, _ in runner.calls],
        runner.writes,
    ) == ([[str(page)] for page in range(1, bad + 1)], [])


@pytest.mark.parametrize("bad", [1, 2], ids=["first-page", "later-page"])
def test_through_run_gh_a_page_that_is_not_json_raises_and_reads_as_no_listing(bad: int) -> None:
    """The same replay through the real `run_gh`, whose own paging ends a listing at a page it
    can't parse and returns exit 0 with what it read before: no issues for a bad first page,
    and only the first hundred for a bad second one. No `gh` runs: its process is stubbed."""
    page = _pages(OPEN_ISSUES[1], "<html>upstream</html>", bad)

    def gh(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        if cmd[-1] == "rate_limit":
            # A quota that resets within two seconds of each refresh keeps `run_gh`'s pause
            # between requests negligible, and is never already past its reset when a loaded
            # host makes the run outlast the first refresh.
            quota = {"limit": 5000, "remaining": 5000, "used": 0, "reset": int(time.time()) + 2}
            return subprocess.CompletedProcess(
                cmd, 0, json.dumps({"resources": {"core": quota}}), ""
            )
        reply = page([arg for arg in cmd if arg.startswith("repos/")])
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return subprocess.CompletedProcess(cmd, 0, text, "")

    store = GitHubRoadmapStore(REPO, board_owner="dan-petty", board_number=2)
    reset_github_rate_limiter()
    try:
        with patch("devops_cli.github.rate_limiter.run_subprocess", side_effect=gh):
            with pytest.raises(GitHubOperationError, match=f"malformed issues \\(page {bad}\\)"):
                store.issues()
    finally:
        reset_github_rate_limiter()


def test_a_listing_reads_on_until_a_page_is_short() -> None:
    store, runner = board_store({"issues?state=all": _pages(OPEN_ISSUES[1], "[]", 3)})
    assert (len(store.issues()), len(runner.calls)) == (200, 3)


def test_a_first_run_whose_issue_listing_is_not_json_refuses_before_any_write() -> None:
    """The reviewers' replay through the plan: the first run's issue listing came back as
    HTML with exit 0 and read as empty, so the run recorded v0.2.25 holding 0 items. The plan
    now raises, naming the read, and nothing is written."""
    store, runner = board_store(
        {
            "fields(first": FIELDS_REPLY,
            BOARD_READ: BoardServer(BOARD),
            "issues?state=all": "<html>upstream</html>",
        }
    )
    with pytest.raises(GitHubOperationError, match=r"malformed issues \(page 1\)"):
        plan_reprioritization(
            store, repo=REPO, config=RoadmapConfig(board=2), now=datetime(2026, 10, 2, tzinfo=UTC)
        )
    assert runner.writes == []


def test_every_read_passes_use_cache_false() -> None:
    store, runner = board_store(
        {
            "milestones?state=all": MILESTONES,
            BOARD_READ: BoardServer(BOARD),
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
        [False] * 14,
        14,
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
            BOARD_READ: BoardServer(BOARD),
        }
    )
    changes = store.changes_since(datetime(2026, 10, 1, 22, 0, tzinfo=UTC))
    assert (
        [args for args, _ in runner.calls if "issues/events" in args[-1]],
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
    store, _ = board_store({"issues/events": [reopened, *EVENTS], BOARD_READ: BoardServer(BOARD)})
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


# ── Board shape, cards, issues and files (#739) ───────────────────────────────
# The GraphQL replies follow the shape of GitHub's ProjectV2 schema; the option ids are the
# recorded board's (`project-field-list.json`) and the colors and descriptions are the ones
# the board template gave those options.

STATUS_NODE = {
    "id": "PVTSSF_lAHOAHXnKc4BiwcgzhhnQg8",
    "name": "Status",
    "dataType": "SINGLE_SELECT",
    "options": [
        {"id": "5b8424c8", "name": "Todo", "color": "GRAY", "description": ""},
        {
            "id": "82b128b7",
            "name": "Backlog",
            "color": "GRAY",
            "description": "Queued backlog items awaiting milestone assignment",
        },
        {
            "id": "89415499",
            "name": "Ready",
            "color": "BLUE",
            "description": "Scoped and ready for implementation",
        },
        {
            "id": "1cb0cdfe",
            "name": "In Progress",
            "color": "YELLOW",
            "description": "Actively under active development (WIP)",
        },
        {
            "id": "77269eb5",
            "name": "In Review",
            "color": "PURPLE",
            "description": "Pull Request opened undergoing multi-persona review & CI",
        },
        {
            "id": "82c424e4",
            "name": "Done",
            "color": "GREEN",
            "description": "Merged into release branch and verified",
        },
    ],
}
FIELD_NODES = [
    {"id": "PVTF_lAHOAHXnKc4BiwcgzhhnQg0", "name": "Title", "dataType": "TITLE"},
    STATUS_NODE,
    {
        "id": "PVTSSF_category",
        "name": "Category",
        "dataType": "SINGLE_SELECT",
        "options": [{"id": "f1", "name": "Quick Win", "color": "GREEN", "description": ""}],
    },
    {"id": "PVTF_jobrecord", "name": "Job record", "dataType": "TEXT"},
]
PROJECTS = {
    "projects": [
        {
            "id": "PVT_kwHOAHXnKc4Biwcg",
            "number": 2,
            "title": "DevOps CLI — Enterprise Development & Release Roadmap",
            "url": "https://github.com/users/dan-petty/projects/2",
        }
    ],
    "totalCount": 1,
}


def owned_board(selection: str, nodes: list[Any]) -> dict[str, Any]:
    connection = {"totalCount": len(nodes), "nodes": nodes}
    return {"data": {"repositoryOwner": {"projectV2": {selection: connection}}}}


def updated_field(node: dict[str, Any]) -> dict[str, Any]:
    return {"data": {"updateProjectV2Field": {"projectV2Field": node}}}


FIELDS_REPLY = owned_board("fields", FIELD_NODES)


def test_board_fields_come_from_graphql_with_option_colors_and_descriptions() -> None:
    store, runner = board_store({"fields(first": FIELDS_REPLY})
    fields = store.board_fields()
    status = next(f for f in fields if f.name == "Status")
    args = runner.calls[0][0]
    assert (
        args[:3] + args[4:],
        [(f.name, f.single_select) for f in fields],
        (status.options[1].id, status.options[1].color, status.options[1].description),
    ) == (
        ["api", "graphql", "-f", "-f", "owner=dan-petty", "-F", "number=2", "-F", "first=100"],
        [("Title", False), ("Status", True), ("Category", True), ("Job record", False)],
        ("82b128b7", "GRAY", "Queued backlog items awaiting milestone assignment"),
    )


def test_a_short_field_listing_raises() -> None:
    reply = owned_board("fields", FIELD_NODES)
    reply["data"]["repositoryOwner"]["projectV2"]["fields"]["totalCount"] = 9
    store, _ = board_store({"fields(first": reply})
    with pytest.raises(GitHubOperationError, match="Read 4 of 9"):
        store.board_fields()


# The input fields GitHub's public GraphQL schema gives `ProjectV2SingleSelectFieldOptionInput`,
# the type `createProjectV2Field` and `updateProjectV2Field` both take options as. It has no id,
# and GitHub rejects a request that sends a field the type doesn't define.
SCHEMA_OPTION_INPUT_FIELDS = ["color", "description", "name"]


def test_the_option_update_request_sends_only_the_input_fields_the_schema_defines() -> None:
    """Options read from the board carry their ids; the request sends none of them (#739)."""
    read = [FieldOption.model_validate(option) for option in STATUS_NODE["options"]]
    blocked = FieldOption(name="Blocked", color="RED", description="Waiting outside the roadmap")
    request = option_update_request(str(STATUS_NODE["id"]), [*read, blocked])
    sent = request["variables"]["options"]
    assert (
        "[ProjectV2SingleSelectFieldOptionInput!]!" in request["query"],
        request["variables"]["fieldId"],
        [sorted(option) for option in sent],
        sent[1],
        sent[-1],
    ) == (
        True,
        STATUS_NODE["id"],
        [SCHEMA_OPTION_INPUT_FIELDS] * 7,
        {
            "name": "Backlog",
            "color": "GRAY",
            "description": "Queued backlog items awaiting milestone assignment",
        },
        {"name": "Blocked", "color": "RED", "description": "Waiting outside the roadmap"},
    )


def test_delete_field_deletes_the_field_by_its_node_id() -> None:
    store, runner = board_store({"fields(first": FIELDS_REPLY, "field-delete": ""})
    store.delete_field("Category")
    with pytest.raises(GitHubOperationError, match="no 'Effort' field"):
        store.delete_field("Effort")
    assert runner.writes == [["project", "field-delete", "--id", "PVTSSF_category"]]


def test_cards_are_everything_on_the_board() -> None:
    store, _ = board_store({BOARD_READ: BoardServer(BOARD)})
    assert [(c.kind, c.number, c.repository, c.status) for c in store.cards()] == [
        (CardKind.ISSUE, 737, REPO, "Done"),
        (CardKind.PULL_REQUEST, 246, REPO, "Done"),
        (CardKind.DRAFT_ISSUE, None, None, "Backlog"),
        (CardKind.ISSUE, 540, "example/other-repo", "Backlog"),
    ]


def test_a_card_field_is_set_by_node_ids_then_recorded() -> None:
    store, runner = board_store(
        {
            "project list": PROJECTS,
            "fields(first": FIELDS_REPLY,
            BOARD_READ: BoardServer(BOARD),
            "item-edit": "",
        }
    )
    draft = next(card for card in store.cards() if card.kind is CardKind.DRAFT_ISSUE)
    store.set_card_field(draft, ItemField.STATUS, "Ready")
    edit = ["project", "item-edit", "--id", draft.id, "--project-id", "PVT_kwHOAHXnKc4Biwcg"]
    assert runner.writes == [
        [*edit, "--field-id", STATUS_NODE["id"], "--single-select-option-id", "89415499"],
        [*edit, "--field-id", "PVTF_jobrecord", "--text", '{"Status": "Ready"}'],
    ]


def test_a_card_write_to_the_release_raises_before_any_read() -> None:
    store, runner = board_store({})
    card = Card(id="PVTI_x", kind=CardKind.ISSUE, number=1)
    with pytest.raises(GitHubOperationError, match="not a board field"):
        store.set_card_field(card, ItemField.RELEASE, "v0.2.25")
    assert runner.calls == []


def test_remove_card_deletes_the_board_item_by_id() -> None:
    store, runner = board_store({BOARD_READ: BoardServer(BOARD), "item-delete": ""})
    card = store.cards()[0]
    store.remove_card(card)
    with pytest.raises(GitHubOperationError, match="not on the board"):
        store.remove_card(card.model_copy(update={"id": "PVTI_gone"}))
    assert runner.writes == [
        ["project", "item-delete", "2", "--owner", "dan-petty", "--id", card.id]
    ]


def test_board_finds_the_number_among_the_owners_boards() -> None:
    store, runner = board_store({"project list": PROJECTS})
    missing = GitHubRoadmapStore(REPO, board_owner="dan-petty", board_number=7, runner=runner)
    found = store.board()
    assert (found.id if found else None, missing.board(), runner.calls[0][0]) == (
        "PVT_kwHOAHXnKc4Biwcg",
        None,
        [
            "project",
            "list",
            "--owner",
            "dan-petty",
            "--closed",
            "--format",
            "json",
            "--limit",
            "100",
        ],
    )


def test_a_short_board_listing_raises() -> None:
    store, _ = board_store({"project list": {**PROJECTS, "totalCount": 120}})
    with pytest.raises(GitHubOperationError, match="Read 1 of 120"):
        store.board()


def test_create_issue_posts_its_title_body_and_labels() -> None:
    opened = {**OPEN_ISSUES[1], "number": 950, "title": "Bare-Metal OS Installers"}
    store, runner = board_store({"-X POST": opened})
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


def test_close_issue_comments_then_closes_for_its_reason() -> None:
    store, runner = board_store(
        {"-X POST": {}, "-X PATCH": {}, f"api repos/{REPO}/issues/917": OPEN_ISSUES[1]}
    )
    store.close_issue(917, CloseReason.NOT_PLANNED, "Not planned (ADR 0001).")
    assert runner.writes == [
        [
            "api",
            "-X",
            "POST",
            f"repos/{REPO}/issues/917/comments",
            "-f",
            "body=Not planned (ADR 0001).",
        ],
        [
            "api",
            "-X",
            "PATCH",
            f"repos/{REPO}/issues/917",
            "-f",
            "state=closed",
            "-f",
            "state_reason=not_planned",
        ],
    ]


def test_closing_a_pull_request_raises_without_writing() -> None:
    store, runner = board_store({f"api repos/{REPO}/issues/918": OPEN_ISSUES[0]})
    with pytest.raises(GitHubOperationError, match="pull request"):
        store.close_issue(918, CloseReason.NOT_PLANNED, "no")
    assert runner.writes == []


def test_delete_release_deletes_its_milestone_by_number() -> None:
    store, runner = board_store({"milestones?state=all": MILESTONES, "-X DELETE": ""})
    store.delete_release("0.2.25")
    with pytest.raises(GitHubOperationError, match="No Release"):
        store.delete_release("9.9.9")
    assert runner.writes == [["api", "-X", "DELETE", f"repos/{REPO}/milestones/43"]]


def test_issues_read_every_state_and_drop_pull_requests() -> None:
    store, runner = board_store({"issues?state=all": ISSUES_IN_RELEASE + OPEN_ISSUES})
    numbers = [issue.number for issue in store.issues()]
    assert (
        918 in numbers,
        len(numbers) < len(ISSUES_IN_RELEASE + OPEN_ISSUES),
        runner.calls[0][0][1],
    ) == (
        False,
        True,
        f"repos/{REPO}/issues?state=all&per_page=100&page=1",
    )


def test_workflows_come_from_graphql() -> None:
    nodes = [
        {"number": 1, "name": "Item closed", "enabled": True},
        {"number": 4, "name": "Auto-add sub-issues to project", "enabled": True},
    ]
    store, runner = board_store({"workflows(first": owned_board("workflows", nodes)})
    assert ([(w.name, w.enabled) for w in store.workflows()], runner.calls[0][0][-1]) == (
        [("Item closed", True), ("Auto-add sub-issues to project", True)],
        "first=50",
    )


def test_repository_file_reads_raw_contents_at_the_ref() -> None:
    store, runner = board_store({"contents/": "board = 2\n"})
    texts = (
        store.repository_file(".github/roadmap.toml", ref="release/v0.2.25"),
        store.repository_file(".github/roadmap.toml"),
    )
    assert (texts, [args for args, _ in runner.calls]) == (
        ("board = 2\n", "board = 2\n"),
        [
            [
                "api",
                "-H",
                "Accept: application/vnd.github.raw+json",
                f"repos/{REPO}/contents/.github/roadmap.toml?ref=release%2Fv0.2.25",
            ],
            [
                "api",
                "-H",
                "Accept: application/vnd.github.raw+json",
                f"repos/{REPO}/contents/.github/roadmap.toml",
            ],
        ],
    )


def test_a_missing_file_raises_not_found_and_another_failure_raises_as_a_failed_read() -> None:
    missing, _ = board_store({"contents/": (1, "gh: Not Found (HTTP 404)")})
    broken, _ = board_store({"contents/": (1, "gh: Server Error (HTTP 502)")})
    with pytest.raises(GitHubFileNotFoundError, match=r"has no docs/ROADMAP\.md at main"):
        missing.repository_file("docs/ROADMAP.md", ref="main")
    with pytest.raises(GitHubOperationError, match=r"Could not read docs/ROADMAP\.md") as failed:
        broken.repository_file("docs/ROADMAP.md", ref="main")
    assert isinstance(failed.value, GitHubFileNotFoundError) is False


def test_create_board_creates_links_and_gives_the_new_board_the_template_fields() -> None:
    new_status = {
        **STATUS_NODE,
        "id": "PVTSSF_new",
        "options": [
            {"id": "aa", "name": "Todo", "color": "GRAY", "description": ""},
            {"id": "bb", "name": "In Progress", "color": "YELLOW", "description": ""},
            {"id": "cc", "name": "Done", "color": "GREEN", "description": ""},
        ],
    }
    created = {"id": "PVT_new", "number": 3, "title": "Roadmap", "url": "https://github.com/x"}
    runner: RecordedGh  # the stdin reply below reads the runner's own requests
    store, runner = board_store(
        {
            "project create": created,
            "project link": "",
            "fields(first": owned_board("fields", [FIELD_NODES[0], new_status]),
            "--input": lambda _: (
                updated_field(new_status)
                if "updateProjectV2Field" in runner.inputs()[-1]["query"]
                else {"data": {}}
            ),
        }
    )
    specs = [
        FieldSpec(
            name="Status",
            single_select=True,
            options=(
                FieldOption(name="New", color="GRAY", description="Not yet ready"),
                FieldOption(name="In Progress", color="YELLOW", description="WIP"),
                FieldOption(name="Done", color="GREEN", description="Closed"),
            ),
        ),
        FieldSpec(name="Value", single_select=True, options=(FieldOption(name="High"),)),
        FieldSpec(name="Job record"),
    ]
    board = store.create_board("Roadmap", specs)
    requests = runner.inputs()
    assert (
        board.number,
        [args[:2] for args in runner.writes],
        [o["name"] for o in requests[0]["variables"]["options"]],
        [
            sorted(option)
            for option in (
                *requests[0]["variables"]["options"],
                *requests[1]["variables"]["input"]["singleSelectOptions"],
            )
        ],
        [request["variables"]["input"]["name"] for request in requests[1:]],
        [request["variables"]["input"]["dataType"] for request in requests[1:]],
    ) == (
        3,
        [
            ["project", "create"],
            ["project", "link"],
            ["api", "graphql"],
            ["api", "graphql"],
            ["api", "graphql"],
        ],
        ["New", "In Progress", "Done"],
        [SCHEMA_OPTION_INPUT_FIELDS] * 4,
        ["Value", "Job record"],
        ["SINGLE_SELECT", "TEXT"],
    )


def test_through_run_gh_board_creation_paces_every_write() -> None:
    """Through the real `run_gh` with gh's process stubbed (#1125): `project create`, `project
    link` and the three field writes sent as `gh api graphql --input -` acquire as writes, and
    the field listing as a read."""
    new_status = {**STATUS_NODE, "id": "PVTSSF_new"}
    created = {"id": "PVT_new", "number": 3, "title": "Roadmap", "url": "https://github.com/x"}

    def gh(
        cmd: list[str], *, input: str | None = None, **_: Any
    ) -> subprocess.CompletedProcess[str]:
        command = " ".join(cmd)
        if "project create" in command:
            reply: Any = created
        elif "project link" in command:
            reply = ""
        elif "--input" in cmd:
            reply = updated_field(new_status) if "updateProjectV2Field" in (input or "") else {}
        else:
            reply = owned_board("fields", [FIELD_NODES[0], new_status])
        return subprocess.CompletedProcess(cmd, 0, json.dumps(reply) if reply else "", "")

    specs = [
        FieldSpec(name="Status", single_select=True, options=(FieldOption(name="New"),)),
        FieldSpec(name="Value", single_select=True, options=(FieldOption(name="High"),)),
        FieldSpec(name="Job record"),
    ]
    store = GitHubRoadmapStore(REPO, board_owner="dan-petty", board_number=2)
    with (
        patch("devops_cli.github.rate_limiter._burst_protected_subprocess", side_effect=gh),
        patch.object(GitHubRateLimiter, "acquire", autospec=True, return_value=0.0) as acquire,
    ):
        board = store.create_board("Roadmap", specs)
    assert (board.number, [call.kwargs["is_mutation"] for call in acquire.call_args_list]) == (
        3,
        [True, True, False, True, True, True],
    )


# ── What the release rules read and write (#740) ──────────────────────────────
# Recorded from dan-petty/devops-cli on 2026-10-02: #743's issue (it is blocked-by nothing yet,
# so it stands in for the dependency an issue's `blocked_by` listing returns), the Status of
# #824 on board 2, the open pull requests, v0.2.24's release pull request (#905, merged), the
# published GitHub Release v0.2.24, the default branch, `release/v0.2.25` and #844's own events.
# The run record card is the recorded draft issue under the run record's title.

ISSUE_743 = recorded("issue-743.json")
STATUS_824 = recorded("graphql-status-824.json")
RELEASE_PRS_37 = recorded("graphql-release-prs-37.json")
OPEN_PRS = recorded("graphql-open-prs.json")
GITHUB_RELEASE = recorded("release-v0.2.24.json")
DEFAULT_BRANCH = recorded("graphql-default-branch.json")
RELEASE_BRANCH = recorded("git-ref-release-v0.2.25.json")
ISSUE_844_EVENTS = recorded("issue-844-events.json")
NOT_FOUND = (1, "gh: Not Found (HTTP 404)")


def test_dependencies_read_the_blocked_by_listing_with_each_issues_repository_and_release() -> None:
    foreign = {
        **ISSUE_743,
        "number": 12,
        "state": "closed",
        "html_url": "https://github.com/example/other/issues/12",
        "repository_url": "https://api.github.com/repos/example/other",
        "milestone": None,
    }
    store, runner = board_store({"dependencies/blocked_by": [ISSUE_743, foreign]})
    assert (
        [(d.number, d.repository, d.state, d.release) for d in store.dependencies(740)],
        runner.calls[0][0][:3],
    ) == (
        [
            (743, REPO, GitHubState.OPEN, "v0.2.26"),
            (12, "example/other", GitHubState.CLOSED, None),
        ],
        ["api", f"repos/{REPO}/issues/740/dependencies/blocked_by?per_page=100&page=1"],
    )


def _status_cards(*cards: dict[str, Any]) -> dict[str, Any]:
    reply: dict[str, Any] = deepcopy(STATUS_824)
    items = reply["data"]["repository"]["issue"]["projectItems"]
    items["nodes"] = [*cards, *items["nodes"]]
    items["totalCount"] = len(items["nodes"])
    return reply


def test_status_changed_at_is_the_status_values_updated_at_on_the_configured_board() -> None:
    other_board = {
        "project": {"number": 9, "owner": {"login": "dan-petty"}},
        "fieldValueByName": {"updatedAt": "2026-09-01T00:00:00Z"},
    }
    store, runner = board_store({"projectItems(first": _status_cards(other_board)})
    no_card = GitHubRoadmapStore(
        REPO,
        board_owner="dan-petty",
        board_number=3,
        runner=RecordedGh({"projectItems(first": _status_cards()}),
    )
    assert (
        store.status_changed_at(824),
        no_card.status_changed_at(824),
        runner.calls[0][0][-4:],
    ) == (
        datetime(2026, 10, 1, 20, 13, 23, tzinfo=UTC),
        None,
        ["-F", "number=824", "-F", "first=20"],
    )


def _pull_request_node(number: int, **changes: Any) -> dict[str, Any]:
    node = deepcopy(RELEASE_PRS_37["data"]["repository"]["milestone"]["pullRequests"]["nodes"][0])
    return {**node, "number": number, **changes}


def test_open_pull_requests_carry_their_last_update_and_last_commit() -> None:
    reply: dict[str, Any] = deepcopy(OPEN_PRS)
    connection = reply["data"]["repository"]["pullRequests"]
    connection["nodes"] = [_pull_request_node(964, state="OPEN", body="Closes #740")]
    connection["totalCount"] = 1
    store, runner = board_store({"openPrs": reply})
    empty, _ = board_store({"openPrs": OPEN_PRS})
    found = store.open_pull_requests()
    assert (
        [(p.number, p.state, p.body, p.updated_at, p.last_commit_at) for p in found],
        empty.open_pull_requests(),
        runner.calls[0][0][-2:],
    ) == (
        [
            (
                964,
                PullRequestState.OPEN,
                "Closes #740",
                datetime(2026, 10, 1, 22, 39, 30, tzinfo=UTC),
                datetime(2026, 10, 1, 22, 25, 55, tzinfo=UTC),
            )
        ],
        [],
        ["-F", "first=100"],
    )


def test_a_pull_request_listing_longer_than_one_read_raises() -> None:
    reply: dict[str, Any] = deepcopy(OPEN_PRS)
    reply["data"]["repository"]["pullRequests"]["totalCount"] = 101
    store, _ = board_store({"openPrs": reply})
    with pytest.raises(GitHubOperationError, match="Read 0 of 101"):
        store.open_pull_requests()


def test_open_pull_requests_combines_open_and_recent_merged() -> None:
    dual_reply = {
        "data": {
            "repository": {
                "openPrs": {
                    "totalCount": 1,
                    "nodes": [_pull_request_node(100, state="OPEN", body="Closes #1")],
                },
                "recentPrs": {
                    "totalCount": 500,
                    "nodes": [_pull_request_node(200, state="MERGED", body="Fixes #2")],
                },
            }
        }
    }
    store, _ = board_store({"openPrs": dual_reply})
    found = store.open_pull_requests()
    assert [p.number for p in found] == [100, 200]


def test_release_pull_requests_are_the_milestones_release_labeled_pull_requests() -> None:
    store, runner = board_store(
        {"milestones?state=all": MILESTONES, "milestone(number": RELEASE_PRS_37}
    )
    found = store.release_pull_requests("0.2.24")
    with pytest.raises(GitHubOperationError, match="No Release"):
        store.release_pull_requests("9.9.9")
    query = runner.calls[1][0]
    assert (
        [(p.number, p.state, p.base, p.labels, p.release) for p in found],
        query[-4:],
        'labels: ["release"]' in " ".join(query),
    ) == (
        [(905, PullRequestState.MERGED, "main", ("release",), "v0.2.24")],
        ["-F", "number=37", "-F", "first=100"],
        True,
    )


@pytest.mark.parametrize(
    ("reply", "published"),
    [(GITHUB_RELEASE, True), ({**GITHUB_RELEASE, "draft": True}, False), (NOT_FOUND, False)],
    ids=["published", "draft", "missing"],
)
def test_release_published_reads_the_github_release_by_its_tag(reply: Any, published: bool) -> None:
    store, runner = board_store({"releases/tags/": reply})
    assert (store.release_published("0.2.24"), runner.calls[0][0]) == (
        published,
        ["api", f"repos/{REPO}/releases/tags/v0.2.24"],
    )


def test_a_github_release_that_cannot_be_read_raises() -> None:
    store, _ = board_store({"releases/tags/": (1, "gh: Server Error (HTTP 500)")})
    with pytest.raises(GitHubOperationError, match=r"GitHub Release v0\.2\.24"):
        store.release_published("v0.2.24")


def test_branches_are_read_by_their_exact_ref_and_created_at_a_commit() -> None:
    store, runner = board_store(
        {
            "defaultBranchRef": DEFAULT_BRANCH,
            "ref/heads/release/v0.2.25": RELEASE_BRANCH,
            "ref/heads/release/v0.2.26": NOT_FOUND,
            "git/refs": {},
        }
    )
    head = store.default_branch()
    read = (store.branch("release/v0.2.25"), store.branch("release/v0.2.26"))
    store.create_branch("release/v0.2.26", head.sha)
    assert ((head.name, head.sha), read, runner.writes) == (
        ("main", "e6ce3db5b7a61a17217c6a590b0f33c70438fed6"),
        ("c279c1883ccb1e300624531d7181d16dafbcdf00", None),
        [
            [
                "api",
                "-X",
                "POST",
                f"repos/{REPO}/git/refs",
                "-f",
                "ref=refs/heads/release/v0.2.26",
                "-f",
                f"sha={head.sha}",
            ]
        ],
    )


def test_comments_on_reads_every_comment_of_the_issue_oldest_first() -> None:
    store, runner = board_store({"issues/844/comments": recorded("issue-844-comments.json")})
    (comment,) = store.comments_on(844)
    assert (
        comment.startswith("**Placement (2026-10-02):** moved from v0.2.28"),
        runner.calls[0][0],
    ) == (
        True,
        ["api", f"repos/{REPO}/issues/844/comments?per_page=100&page=1"],
    )


def test_comment_posts_one_comment() -> None:
    store, runner = board_store({"-X POST": {}})
    store.comment(740, "Moved to v0.2.26: it is Blocked and had not started.")
    assert runner.writes == [
        [
            "api",
            "-X",
            "POST",
            f"repos/{REPO}/issues/740/comments",
            "-f",
            "body=Moved to v0.2.26: it is Blocked and had not started.",
        ]
    ]


def test_set_marks_merges_the_marks_into_the_job_record_the_board_holds_in_one_write() -> None:
    board = on_board()
    board["items"][0]["job record"] = '{"Pending": "{}", "Release": "v0.2.25"}'
    store, runner = board_store(
        {"field-list": fields_with_job_record(), BOARD_READ: BoardServer(board), "item-edit": ""}
    )
    store.set_marks(board_item(737), {JobMark.ADMITTED: "v0.2.25", JobMark.PENDING: None})
    assert [(args[8:10], json.loads(args[-1])) for args in runner.writes] == [
        (["Job record", "--text"], {"Admitted": "v0.2.25", "Pending": None, "Release": "v0.2.25"})
    ]


def test_set_marks_records_and_forgets_field_values_in_the_same_write() -> None:
    """The record of a field write a job began goes back as it was: a value it held, or none,
    and a key this version doesn't know survives."""
    board = on_board()
    board["items"][0]["job record"] = (
        '{"NeedsSplit": "yes", "Pending": "{}", "Release": "v0.2.26", "Status": "Ready"}'
    )
    store, runner = board_store(
        {"field-list": fields_with_job_record(), BOARD_READ: BoardServer(board), "item-edit": ""}
    )
    store.set_marks(
        board_item(737),
        {JobMark.PENDING: None},
        recorded={ItemField.STATUS: "In Progress"},
        forgotten=(ItemField.RELEASE,),
    )
    assert [(args[8:10], json.loads(args[-1])) for args in runner.writes] == [
        (["Job record", "--text"], {"NeedsSplit": "yes", "Pending": None, "Status": "In Progress"})
    ]


def test_every_job_record_write_keeps_the_keys_this_version_does_not_know() -> None:
    """A newer version's key survives this version's writes: none rebuilds the record from
    only the keys it read."""
    board = on_board()
    board["items"][0]["job record"] = '{"Admitted": "v0.2.25", "NeedsSplit": "yes"}'
    run_record = with_run_record('{"Started": "v0.2.25", "Cadence": "weekly"}')
    store, runner = board_store(
        {
            "project list": PROJECTS,
            "fields(first": FIELDS_REPLY,
            "field-list": fields_with_job_record(),
            BOARD_READ: BoardServer(board),
            "item-edit": "",
        }
    )
    store.set_marks(board_item(737), {JobMark.PENDING: "{}"})
    store.set_field(board_item(737), ItemField.PRIORITY, "P1-High")
    marks_and_field = [json.loads(args[-1]) for args in runner.writes if args[-2] == "--text"]
    runner.replies[BOARD_READ] = BoardServer(run_record)
    store.set_run_record({JobMark.STARTED: "v0.2.26"})
    assert (marks_and_field, json.loads(runner.writes[-1][-1])) == (
        [
            {"Admitted": "v0.2.25", "NeedsSplit": "yes", "Pending": "{}"},
            {"Admitted": "v0.2.25", "NeedsSplit": "yes", "Priority": "P1-High"},
        ],
        {"Cadence": "weekly", "Started": "v0.2.26"},
    )


def test_set_marks_raises_before_any_write_for_an_item_off_the_board() -> None:
    store, runner = board_store(
        {"field-list": fields_with_job_record(), BOARD_READ: BoardServer(BOARD)}
    )
    with pytest.raises(GitHubOperationError, match="#739 is not on the board"):
        store.set_marks(board_item(739), {JobMark.NUDGED: "2026-10-02T00:00:00+00:00"})
    assert runner.writes == []


def with_run_record(record: str | None) -> dict[str, Any]:
    """The recorded board with the run record card: a draft issue, as the recorded draft is."""
    board: dict[str, Any] = deepcopy(BOARD)
    draft = deepcopy(next(i for i in board["items"] if i["content"]["type"] == "DraftIssue"))
    draft["id"] = "PVTI_runrecord"
    draft["content"].update(id="DI_runrecord", title="Roadmap run record")
    draft["title"] = "Roadmap run record"
    draft.pop("status")
    if record is not None:
        draft["job record"] = record
    board["items"].append(draft)
    board["totalCount"] = len(board["items"])
    return board


def test_the_run_record_is_the_job_record_of_the_draft_card_titled_for_it() -> None:
    """The board's other draft has a title of its own, so it is not the run record card."""
    store, _ = board_store({BOARD_READ: BoardServer(with_run_record('{"Started": "v0.2.25"}'))})
    without, _ = board_store({BOARD_READ: BoardServer(BOARD)})
    assert (store.run_record(), without.run_record()) == ({JobMark.STARTED: "v0.2.25"}, {})


def test_set_run_record_creates_its_card_once_then_edits_its_job_record_by_node_id() -> None:
    listings = iter([BOARD, with_run_record(None), with_run_record('{"Started": "v0.2.25"}')])
    replies = {
        "project list": PROJECTS,
        "fields(first": FIELDS_REPLY,
        BOARD_READ: BoardServer(lambda: next(listings)),
        "item-create": "",
        "item-edit": "",
    }
    store, runner = board_store(replies)
    store.set_run_record({JobMark.STARTED: "v0.2.25"})
    store.set_run_record({JobMark.STARTED: "v0.2.26"})
    edit = ["project", "item-edit", "--id", "PVTI_runrecord", "--project-id"]
    assert runner.writes == [
        [
            "project",
            "item-create",
            "2",
            "--owner",
            "dan-petty",
            "--title",
            "Roadmap run record",
            "--body",
            CONST_ROADMAP_RUN_RECORD_BODY,
        ],
        [
            *edit,
            "PVT_kwHOAHXnKc4Biwcg",
            "--field-id",
            "PVTF_jobrecord",
            "--text",
            '{"Started": "v0.2.25"}',
        ],
        [
            *edit,
            "PVT_kwHOAHXnKc4Biwcg",
            "--field-id",
            "PVTF_jobrecord",
            "--text",
            '{"Started": "v0.2.26"}',
        ],
    ]


def test_set_run_record_raises_when_the_card_it_created_is_not_listed() -> None:
    store, _ = board_store(
        {
            "project list": PROJECTS,
            "fields(first": FIELDS_REPLY,
            BOARD_READ: BoardServer(BOARD),
            "item-create": "",
        }
    )
    with pytest.raises(GitHubOperationError, match="does not list the run record card"):
        store.set_run_record({JobMark.STARTED: "v0.2.25"})


def test_release_changes_read_one_issues_events_for_its_joins_and_leaves() -> None:
    """#844: a person placed it in v0.2.28, then moved it to the backlog."""
    store, runner = board_store({"issues/844/events": ISSUE_844_EVENTS})
    found = store.release_changes(844)
    assert (
        [(c.kind, c.number, c.release, c.actor, c.at) for c in found],
        runner.calls[0][0],
    ) == (
        [
            (
                ChangeKind.JOINED_RELEASE,
                844,
                "v0.2.28",
                "dan-petty",
                datetime(2026, 10, 1, 21, 31, 22, tzinfo=UTC),
            ),
            (
                ChangeKind.LEFT_RELEASE,
                844,
                "v0.2.28",
                "dan-petty",
                datetime(2026, 10, 2, 3, 26, 46, tzinfo=UTC),
            ),
        ],
        ["api", f"repos/{REPO}/issues/844/events?per_page=100&page=1"],
    )


def test_a_milestone_change_carries_the_release_now_and_the_items_job_record() -> None:
    """`value` is the issue's milestone when read, so it compares with the job record."""
    joined = deepcopy(
        next(e for e in EVENTS if e["event"] == "milestoned" and e["issue"]["number"] == 912)
    )
    joined["issue"]["milestone"] = {"title": "v0.2.24"}
    board = on_board(912)
    board["items"][-1]["job record"] = '{"Release": "v0.2.24"}'
    store, _ = board_store({"issues/events": [joined], BOARD_READ: BoardServer(board)})
    (change,) = store.changes_since(datetime(2026, 10, 1, tzinfo=UTC))
    assert (change.kind, change.release, change.field, change.value, change.job_record) == (
        ChangeKind.JOINED_RELEASE,
        "v0.2.24",
        ItemField.RELEASE,
        "v0.2.24",
        {ItemField.RELEASE: "v0.2.24"},
    )


# ── What intake reads and writes (#742) ───────────────────────────────────────


def issue_payload(number: int, **changes: Any) -> dict[str, Any]:
    """The recorded open issue #917 as issue `number`, with its node id."""
    return {**OPEN_ISSUES[1], "number": number, "node_id": f"I_kw{number}", **changes}


def test_close_as_duplicate_comments_then_closes_with_the_originals_node_id() -> None:
    store, runner = board_store(
        {
            "-X POST": {},
            "--input": {"data": {"closeIssue": {"issue": {"number": 950}}}},
            f"api repos/{REPO}/issues/950": issue_payload(950),
            f"api repos/{REPO}/issues/742": issue_payload(742),
        }
    )
    store.close_as_duplicate(950, 742, "Duplicate of #742.")
    (request,) = runner.inputs()
    assert (runner.writes[0][3:], "DUPLICATE" in request["query"], request["variables"]) == (
        [f"repos/{REPO}/issues/950/comments", "-f", "body=Duplicate of #742."],
        True,
        {"issue": "I_kw950", "original": "I_kw742"},
    )


def test_close_as_duplicate_without_a_comment_writes_only_the_close() -> None:
    store, runner = board_store(
        {
            "--input": {"data": {"closeIssue": {"issue": {"number": 950}}}},
            f"api repos/{REPO}/issues/950": issue_payload(950),
            f"api repos/{REPO}/issues/742": issue_payload(742),
        }
    )
    store.close_as_duplicate(950, 742, None)
    assert ([w for w in runner.writes if "comments" in " ".join(w)], len(runner.inputs())) == (
        [],
        1,
    )


def test_close_as_duplicate_refuses_a_pull_request_before_any_write() -> None:
    store, runner = board_store(
        {
            f"api repos/{REPO}/issues/918": OPEN_ISSUES[0],
            f"api repos/{REPO}/issues/742": issue_payload(742),
        }
    )
    with pytest.raises(GitHubOperationError, match="pull request"):
        store.close_as_duplicate(742, 918, "no")
    assert runner.writes == []


def _timeline(nodes: list[dict[str, Any]], total: int | None = None) -> dict[str, Any]:
    connection = {"nodes": nodes, "totalCount": len(nodes) if total is None else total}
    return {"data": {"repository": {"issue": {"timelineItems": connection}}}}


def test_closures_read_the_timelines_closes_and_reopens_oldest_first() -> None:
    nodes = [
        {
            "__typename": "ClosedEvent",
            "createdAt": "2026-10-01T10:00:00Z",
            "stateReason": "DUPLICATE",
            "duplicateOf": {"number": 742},
        },
        {"__typename": "ReopenedEvent", "createdAt": "2026-10-01T11:00:00Z"},
    ]
    store, runner = board_store({"timelineItems": _timeline(nodes)})
    closures = store.closures(950)
    assert (
        [(c.kind, c.at.hour, c.reason, c.duplicate_of) for c in closures],
        runner.calls[0][0][-2:],
    ) == (
        [(ChangeKind.CLOSED, 10, "duplicate", 742), (ChangeKind.REOPENED, 11, None, None)],
        ["-F", "number=950"],
    )


def test_closures_past_the_connection_limit_raise() -> None:
    store, _ = board_store({"timelineItems": _timeline([], total=101)})
    with pytest.raises(GitHubOperationError, match="Read 0 of 101"):
        store.closures(950)


def test_label_issue_posts_one_label_and_keeps_the_others() -> None:
    store, runner = board_store({"-X POST": []})
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
    store, runner = board_store({"api ": reply})
    found = store.evidence_holds(Evidence(kind=EvidenceKind(kind), value=value))
    assert (found, endpoint in runner.calls[0][0][-1]) == (holds, True)


def test_evidence_with_a_path_in_its_value_never_leaves_its_endpoint() -> None:
    store, runner = board_store({"api ": {"sha": "x"}})
    store.evidence_holds(Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="../pulls/1"))
    assert runner.calls[0][0][-1] == f"repos/{REPO}/commits/..%2Fpulls%2F1"


def test_count_issues_reads_rest_search_total_count_for_its_query() -> None:
    store, runner = board_store({"search/issues": {"total_count": 57, "incomplete_results": False}})
    since = datetime(2026, 10, 3, 20, 37, 25, tzinfo=UTC)
    counted = store.count_issues(
        IssueQuery(
            state=GitHubState.CLOSED,
            labels=("source/agent",),
            created_since=since,
            closed_since=since,
            reason=CloseReason.NOT_PLANNED,
            uncommented=True,
        )
    )
    assert (counted, runner.calls[0][0]) == (
        57,
        [
            "api",
            "-X",
            "GET",
            "search/issues",
            "-f",
            f'q=repo:{REPO} is:issue is:closed label:"source/agent" '
            "created:>=2026-10-03T20:37:25+00:00 closed:>=2026-10-03T20:37:25+00:00 "
            'reason:"not planned" comments:0',
            "-F",
            "per_page=1",
        ],
    )


def test_an_incomplete_search_raises_rather_than_undercount() -> None:
    store, _ = board_store({"search/issues": {"total_count": 3, "incomplete_results": True}})
    with pytest.raises(GitHubOperationError, match="incomplete"):
        store.count_issues(IssueQuery(state=GitHubState.OPEN))


def test_issue_records_and_releases_carry_author_and_close_times() -> None:
    closed = {**MILESTONES[0], "state": "closed", "closed_at": "2026-10-03T20:37:25Z"}
    store, _ = board_store(
        {
            "milestones?state=all": [closed],
            "issues?state=all": [
                issue_payload(
                    950,
                    author_association="COLLABORATOR",
                    created_at="2026-10-04T01:00:00Z",
                    closed_at=None,
                )
            ],
        }
    )
    (issue,) = store.issues()
    (release,) = store.releases()
    assert (
        issue.author_association,
        issue.created_at,
        release.closed_at,
    ) == (
        "COLLABORATOR",
        datetime(2026, 10, 4, 1, tzinfo=UTC),
        datetime(2026, 10, 3, 20, 37, 25, tzinfo=UTC),
    )


# ── Merged pull requests (#743) ──


def _closed_pull(number: int, merged: bool = True) -> dict[str, Any]:
    return {
        "number": number,
        "html_url": f"https://github.com/{REPO}/pull/{number}",
        "title": f"feat: {number}",
        "body": f"Closes #{number + 1000}" if number % 2 else None,
        "labels": [{"name": "type/feature"}],
        "milestone": {"title": "v0.2.26"},
        "merged_at": "2026-10-03T12:00:00Z" if merged else None,
        "merge_commit_sha": f"{number:040x}",
        "head": {"sha": f"{number:040x}"[::-1]},
    }


def _closed_pages(bad: int | None = None) -> Callable[[list[str]], Any]:
    """Closed pull requests over three pages, 100, 100 and 5; page `bad` fails."""

    def page(args: list[str]) -> Any:
        (number,) = _query(args, "page")[0]
        if int(number) == bad:
            return (1, "gh: Server Error (HTTP 502)")
        first = (int(number) - 1) * 100 + 1
        size = 100 if int(number) < 3 else 5
        return [_closed_pull(n, merged=n != 7) for n in range(first, first + size)]

    return page


def test_merged_pull_requests_read_every_page_with_each_ones_files() -> None:
    store, runner = board_store(
        {
            "pulls?state=closed": _closed_pages(),
            "/files?": [{"filename": "src/a.py"}, {"filename": "docs/agent/tasks/task-1-a.md"}],
        }
    )
    merged = store.merged_pull_requests("release/v0.2.26")
    first = merged[0]
    assert (
        len(merged),
        [p.number for p in merged][:7],
        (first.url, first.body, first.labels, first.release, first.changed_paths),
        (first.merge_commit, first.head_commit) == (f"{1:040x}", f"{1:040x}"[::-1]),
        runner.calls[0][0][-1].split("&per_page")[0],
        runner.writes,
    ) == (
        204,
        [1, 2, 3, 4, 5, 6, 8],
        (
            f"https://github.com/{REPO}/pull/1",
            "Closes #1001",
            ("type/feature",),
            "v0.2.26",
            ("src/a.py", "docs/agent/tasks/task-1-a.md"),
        ),
        True,
        f"repos/{REPO}/pulls?state=closed&base=release%2Fv0.2.26&sort=created&direction=asc",
        [],
    )


@pytest.mark.parametrize("bad", [1, 2, 3])
def test_a_failed_merged_pull_request_page_raises_and_returns_no_part(bad: int) -> None:
    store, _ = board_store({"pulls?state=closed": _closed_pages(bad), "/files?": []})
    with pytest.raises(
        GitHubOperationError, match=rf"pull requests into release/v0.2.26 \(page {bad}\)"
    ):
        store.merged_pull_requests("release/v0.2.26")


def test_a_failed_files_listing_raises() -> None:
    store, _ = board_store(
        {"pulls?state=closed": _closed_pages(), "/files?": (1, "gh: Server Error (HTTP 502)")}
    )
    with pytest.raises(GitHubOperationError, match=r"#1 files \(page 1\)"):
        store.merged_pull_requests("release/v0.2.26")


def test_is_private_args_and_write_issue_body_args() -> None:
    write_args = write_issue_body_args(REPO, 42, "new body")
    priv_args = is_private_args(REPO)
    owner, name = REPO.split("/", 1)
    assert (
        write_args,
        priv_args,
    ) == (
        ["api", "-X", "PATCH", f"repos/{REPO}/issues/42", "-f", "body=new body"],
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


def test_read_and_write_issue_body_github_store() -> None:
    store, runner = board_store({"-X PATCH": {}, f"api repos/{REPO}/issues/917": OPEN_ISSUES[1]})
    body = store.read_issue_body(917)
    store.write_issue_body(917, "Updated content")
    assert (
        body,
        runner.writes,
    ) == (
        OPEN_ISSUES[1].get("body") or "",
        [["api", "-X", "PATCH", f"repos/{REPO}/issues/917", "-f", "body=Updated content"]],
    )


def test_issue_body_on_pull_request_raises_github_store() -> None:
    store, runner = board_store({f"api repos/{REPO}/issues/918": OPEN_ISSUES[0]})
    with pytest.raises(GitHubOperationError, match="pull request"):
        store.read_issue_body(918)
    with pytest.raises(GitHubOperationError, match="pull request"):
        store.write_issue_body(918, "content")
    assert runner.writes == []


def test_repository_is_private_github_store() -> None:
    store, _ = board_store({"isPrivate": {"data": {"repository": {"isPrivate": True}}}})
    assert store.repository_is_private() is True
