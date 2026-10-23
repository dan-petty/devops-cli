"""GitHub roadmap store over a stub runner that answers with recorded `gh` output.

The recorded listings under `tests/fixtures/roadmap/` come from dan-petty/devops-cli and its
board (project 2), trimmed to the keys the store reads. The milestone listing keeps the
recorded milestones that name a past version, and adds two planning buckets, #47 `2026-10-29`
with a due date and #48 `Q4 hardening` without one. No case runs `gh` or opens a socket.
The store reads its REST listings through the GitHub session (#983): `board_store` answers
them from the same recorded replies through `RunnerSession`, and the tests of paging, early
stops and failed pages run the real session over the `github_api` fake (`over_github`).
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
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest

from devops_cli.config.defaults import DEFAULT_GH_GRAPHQL_BUDGET_FLOOR
from devops_cli.exceptions.git import (
    GitHubFileNotFoundError,
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.exceptions.roadmap import RoadmapCardChangedError
from devops_cli.github.rate_limiter import GitHubRateLimiter
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.board_read import BOARD_CARD_OPERATION, GRAPHQL_BUDGET_OPERATION
from devops_cli.roadmap.github_store import (
    GitHubRoadmapStore,
    card_edit_args,
    is_private_args,
    write_issue_body_args,
)
from devops_cli.roadmap.store import (
    ChangeKind,
    Evidence,
    EvidenceKind,
    GitHubState,
    Item,
    ItemField,
    RefineRecordKey,
    RoadmapStore,
)
from tests.roadmap_board_fake import (
    BOARD_READ,
    BoardServer,
    GitHubFake,
    budget_reply,
    gh_variables,
)
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

ROADMAP_FIXTURES = FIXTURES / "roadmap"
REPO = "dan-petty/devops-cli"
ISSUE_URL = f"https://github.com/{REPO}/issues"


def recorded(name: str) -> Any:
    return json.loads((ROADMAP_FIXTURES / name).read_text(encoding="utf-8"))


MILESTONES = recorded("milestones.json")
BOARD = recorded("project-item-list.json")
FIELDS = recorded("project-field-list.json")
ISSUES_IN_MILESTONE = recorded("issues-milestone-43.json")
OPEN_ISSUES = recorded("issues-open.json")
EVENTS = recorded("issue-events.json")

LISTING_MILESTONES = f"repos/{REPO}/milestones?state=all&per_page=100"
LISTING_IN_MILESTONE = f"repos/{REPO}/issues?milestone=43&state=all&per_page=100"


# The board's node id, as the recorded board listing (`project list`) gives it.
BOARD_ID = "PVT_kwHOAHXnKc4Biwcg"
CARD_737 = BOARD["items"][0]["id"]
JOB_RECORD_ID = "PVTF_jobrecord"


def fields_with_job_record() -> dict[str, Any]:
    listing: dict[str, Any] = deepcopy(FIELDS)
    listing["fields"].append({"id": JOB_RECORD_ID, "name": "Job record", "type": "ProjectV2Field"})
    listing["totalCount"] += 1
    return listing


def graphql_fields(listing: dict[str, Any]) -> dict[str, Any]:
    """The recorded field listing as the store's GraphQL fields query answers it, with the
    board's node id."""
    nodes = [
        {
            "id": board_field["id"],
            "name": board_field["name"],
            "dataType": (
                "SINGLE_SELECT" if board_field["type"] == "ProjectV2SingleSelectField" else "TEXT"
            ),
            "options": board_field.get("options", []),
        }
        for board_field in listing["fields"]
    ]
    connection = {"totalCount": len(nodes), "nodes": nodes}
    return {"data": {"repositoryOwner": {"projectV2": {"id": BOARD_ID, "fields": connection}}}}


ITEM_FIELDS = graphql_fields(fields_with_job_record())
FIELD_IDS = {f["name"]: f["id"] for f in fields_with_job_record()["fields"]}
OPTION_IDS = {
    (f["name"], o["name"]): o["id"] for f in FIELDS["fields"] for o in f.get("options", [])
}


def created_milestone(number: int, title: str, **changes: Any) -> dict[str, Any]:
    """The recorded milestone #43, as GitHub would return it after a write."""
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
        changing = {"POST", "PATCH", "DELETE", "item-edit", "item-add", "item-archive", "--input"}
        return [args for args, _ in self.calls if changing & set(args)]

    def inputs(self) -> list[Any]:
        """The JSON each call sent on stdin, in call order."""
        return [json.loads(kwargs["input"]) for _, kwargs in self.calls if kwargs.get("input")]


def board_store(replies: dict[str, Any]) -> tuple[GitHubRoadmapStore, RecordedGh]:
    runner = RecordedGh(replies)
    return GitHubRoadmapStore(
        REPO, board_owner="dan-petty", board_number=2, runner=runner, session=RunnerSession(runner)
    ), runner


def board_item(number: int, **fields: Any) -> Item:
    """Issue `number` as an Item read from the board: #737's card is the recorded one, with its
    Status and Priority, the others are `on_board`'s `PVTI_<number>`."""
    card = CARD_737 if number == 737 else f"PVTI_{number}"
    recorded = {"status": "Done", "priority": "P1-High"} if number == 737 else {}
    return Item.model_validate(
        {"number": number, "title": f"#{number}", "url": f"{ISSUE_URL}/{number}", "card_id": card}
        | recorded
        | fields
    )


def card_edit(card: str, field_name: str, *change: str) -> list[str]:
    """The id-addressed `item-edit` of `field_name` on `card`."""
    return card_edit_args(card, BOARD_ID, FIELD_IDS[field_name], list(change))


def graphql_kinds(runner: RecordedGh) -> list[str]:
    """Each GraphQL-class command the store sent, by what it is: a board read, a card read, the
    fields, an id-addressed edit, or anything else by its first two arguments."""
    kinds = []
    for args, _ in runner.calls:
        query = gh_variables(args).get("query", "") if args[:2] == ["api", "graphql"] else ""
        if args[0] == "project":
            kinds.append(f"{args[1]} by id" if "--id" in args else args[1])
        elif query:
            kinds.append(
                next(
                    (name for name in ("RoadmapBoardCard", "RoadmapBoard") if name in query),
                    "fields" if "fields(first" in query else query[:40],
                )
            )
    return kinds


# ── Milestones ────────────────────────────────────────────────────────────────


def test_a_milestone_is_found_by_its_exact_title_or_by_its_number() -> None:
    """No title is read as a version: `0.2.25` names no milestone, `v0.2.25` and `43` name #43."""
    store, _ = board_store({"milestones?state=all": MILESTONES})
    found = (store.milestone("v0.2.25"), store.milestone("43"), store.milestone("0.2.25"))
    assert [milestone.number if milestone else None for milestone in found] == [43, 43, None]


def test_milestones_sort_by_due_date_then_by_number_whatever_their_titles() -> None:
    """Every recorded milestone is read, whatever its title; the one with a due date comes
    first, and the others follow by number."""
    store, _ = board_store({"milestones?state=all": MILESTONES})
    milestones = store.milestones()
    numbers = [milestone.number for milestone in milestones]
    assert (
        (milestones[0].title, milestones[0].due_on),
        numbers[1:] == sorted(numbers[1:]),
        "Q4 hardening" in [milestone.title for milestone in milestones],
        len(milestones),
    ) == (("2026-10-29", date(2026, 10, 29)), True, True, len(MILESTONES))


def test_edit_milestone_sends_only_the_fields_it_is_given() -> None:
    store, runner = board_store(
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
    store, runner = board_store({"milestones?state=all": MILESTONES})
    with pytest.raises(GitHubOperationError, match="already has the title 'Q4 hardening'"):
        store.edit_milestone("43", title="Q4 hardening")
    assert runner.writes == []


def test_an_edit_that_names_no_state_sends_no_state() -> None:
    store, runner = board_store(
        {"milestones?state=all": MILESTONES, "-X PATCH": created_milestone(43, "v0.2.25")}
    )
    edited = store.edit_milestone("43", description="new text")
    assert (runner.writes, edited.state) == (
        [["api", "-X", "PATCH", f"repos/{REPO}/milestones/43", "-f", "description=new text"]],
        GitHubState.OPEN,
    )


def test_an_edit_with_nothing_to_change_writes_nothing() -> None:
    store, runner = board_store({"milestones?state=all": MILESTONES})
    assert (store.edit_milestone("43").number, runner.writes) == (43, [])


def test_close_milestone_patches_only_its_state() -> None:
    store, runner = board_store(
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
    store, runner = board_store({"milestones?state=all": MILESTONES})
    with pytest.raises(GitHubOperationError, match="No milestone has the title or number"):
        store.close_milestone("Q5")
    assert runner.writes == []


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
            "issues?state=all": ISSUES_IN_MILESTONE + OPEN_ISSUES,
            "issues/737": ISSUES_IN_MILESTONE[2],
        }
    )
    items = store.items()
    assert (
        [item.number for item in items],
        [content["content"]["type"] for content in BOARD["items"]],
        store.item(246),
        store.item(540),
    ) == ([737], ["Issue", "PullRequest", "DraftIssue", "Issue"], None, None)


def test_items_in_a_milestone_include_a_closed_issue_with_its_state_and_milestone_from_rest() -> (
    None
):
    store, runner = board_store(
        {BOARD_READ: BoardServer(BOARD), "issues?milestone=43": ISSUES_IN_MILESTONE}
    )
    items = store.items(milestone=43)
    assert (
        [
            (item.number, item.state, item.state_reason, item.milestone, item.status, item.priority)
            for item in items
        ],
        [args for args, _ in runner.calls if args[0].startswith(API)],
    ) == (
        [(737, GitHubState.CLOSED, "completed", "v0.2.25", "Done", "P1-High")],
        [[f"{API}/{LISTING_IN_MILESTONE}"]],
    )


def test_backlog_reads_the_open_issues_in_no_milestone() -> None:
    open_on_board = {**ISSUES_IN_MILESTONE[1], "milestone": None}
    store, runner = board_store(
        {BOARD_READ: BoardServer(on_board(739)), "issues?milestone=none": [open_on_board]}
    )
    assert ([item.number for item in store.backlog()], runner.calls[-1][0]) == (
        [739],
        [f"{API}/repos/{REPO}/issues?milestone=none&state=open&per_page=100"],
    )


def test_items_carry_the_body_of_the_listing_they_were_read_from_with_no_request_per_issue() -> (
    None
):
    """The recorded listings hold no body, so one is put into a copy of each (#1539)."""
    in_milestone = {**ISSUES_IN_MILESTONE[2], "body": "Planned text"}
    in_backlog = {**ISSUES_IN_MILESTONE[1], "milestone": None, "body": "Backlog text"}
    store, runner = board_store(
        {
            BOARD_READ: BoardServer(on_board(739)),
            "issues?milestone=43": [in_milestone],
            "issues?milestone=none": [in_backlog],
        }
    )
    planned, backlog = store.items(milestone=43), store.backlog()
    assert (
        [(item.number, item.body) for item in planned],
        [(item.number, item.body) for item in backlog],
        [args[0] for args, _ in runner.calls if args[0].startswith(API)],
    ) == (
        [(737, "Planned text")],
        [(739, "Backlog text")],
        [
            f"{API}/{LISTING_IN_MILESTONE}",
            f"{API}/repos/{REPO}/issues?milestone=none&state=open&per_page=100",
        ],
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
    """A key this version does not know, such as one another version writes, is left out:
    an `OtherTool` mark reads as nothing."""
    board = on_board(739, 768)
    board["items"][-2]["job record"] = '{"Priority": "P1-High", "OtherTool": "x"}'
    board["items"][-1]["job record"] = '{"OtherTool": "y", "refine.body_hash": "b1"}'
    store, _ = board_store(
        {BOARD_READ: BoardServer(board), "issues?state=all": ISSUES_IN_MILESTONE}
    )
    assert [(item.number, item.job_record) for item in store.items()] == [
        (737, {}),
        (739, {ItemField.PRIORITY: "P1-High"}),
        (768, {RefineRecordKey.BODY_HASH: "b1"}),
    ]


@pytest.mark.parametrize(
    "record",
    ["not json", '["Priority", "P1-High"]', '{"Priority": 25}'],
    ids=["not-json", "not-an-object", "a-known-key-without-text"],
)
def test_a_job_record_that_cannot_be_decoded_fails_the_read_and_names_its_card(
    record: str,
) -> None:
    """Read as empty, the card would look as if no job had ever set a field on it."""
    board = on_board(768)
    board["items"][-1]["job record"] = record
    store, runner = board_store(
        {BOARD_READ: BoardServer(board), "issues?state=all": ISSUES_IN_MILESTONE}
    )
    with pytest.raises(GitHubOperationError, match="job record of #768 is not a JSON object"):
        store.items()
    assert runner.writes == []


# ── Item writes ───────────────────────────────────────────────────────────────


def test_a_value_that_is_not_a_board_option_raises_without_reading_the_card() -> None:
    store, runner = board_store({"fields(first": ITEM_FIELDS, BOARD_READ: BoardServer(BOARD)})
    with pytest.raises(GitHubOperationError, match="not a Priority option"):
        store.set_field(board_item(737), ItemField.PRIORITY, "P9-Someday")
    assert (runner.writes, graphql_kinds(runner)) == ([], ["fields"])


def test_setting_priority_records_it_in_the_job_record_then_edits_the_field_by_ids() -> None:
    # The Item was read before its Status was recorded; the record merges into the card's.
    board = on_board()
    board["items"][0]["job record"] = '{"Status": "Done"}'
    store, runner = board_store(
        {"fields(first": ITEM_FIELDS, BOARD_READ: BoardServer(board), "item-edit": ""}
    )
    store.set_field(board_item(737, status="Done"), ItemField.PRIORITY, "P2-Medium")
    record = runner.writes[0][-1]
    assert (runner.writes, json.loads(record)) == (
        [
            card_edit(CARD_737, "Job record", "--text", record),
            card_edit(
                CARD_737,
                "Priority",
                "--single-select-option-id",
                OPTION_IDS["Priority", "P2-Medium"],
            ),
        ],
        {"Priority": "P2-Medium", "Status": "Done"},
    )


def test_a_field_write_sets_marks_in_the_write_that_records_its_value() -> None:
    """The record of the value and the marks go in one write, before the field: a job that
    stops after it finds both, and one that stops before it finds neither."""
    store, runner = board_store(
        {"fields(first": ITEM_FIELDS, BOARD_READ: BoardServer(BOARD), "item-edit": ""}
    )
    store.set_field(
        board_item(737), ItemField.STATUS, "Ready", marks={RefineRecordKey.SECTION_HASH: "s1"}
    )
    assert [args[7:] for args in runner.writes] == [
        [JOB_RECORD_ID, "--text", '{"Status": "Ready", "refine.section_hash": "s1"}'],
        [FIELD_IDS["Status"], "--single-select-option-id", OPTION_IDS["Status", "Ready"]],
    ]


def test_two_writes_from_one_read_keep_both_fields_in_the_job_record() -> None:
    board = on_board()

    def edit_board(args: list[str]) -> str:
        if JOB_RECORD_ID in args:
            board["items"][0]["job record"] = args[-1]
        return ""

    store, runner = board_store(
        {
            "fields(first": ITEM_FIELDS,
            BOARD_READ: BoardServer(board),
            "item-edit": edit_board,
            f"api repos/{REPO}/issues/737": ISSUES_IN_MILESTONE[2],
        }
    )
    item = store.item(737)
    assert item is not None
    store.set_field(item, ItemField.PRIORITY, "P2-Medium")
    store.set_field(item, ItemField.STATUS, "Ready")
    assert (
        item.card_id,
        [json.loads(args[-1]) for args in runner.writes if JOB_RECORD_ID in args],
    ) == (CARD_737, [{"Priority": "P2-Medium"}, {"Priority": "P2-Medium", "Status": "Ready"}])


def test_writing_an_item_that_is_not_on_the_board_raises_without_writing() -> None:
    store, runner = board_store({"fields(first": ITEM_FIELDS, BOARD_READ: BoardServer(BOARD)})
    with pytest.raises(GitHubOperationError, match="#739 is not on the board"):
        store.set_field(board_item(739), ItemField.STATUS, "Ready")
    assert runner.writes == []


def test_an_item_whose_card_holds_another_issue_raises_without_writing() -> None:
    """A card id names one card: an Item whose card id is another issue's is not on the board."""
    store, runner = board_store({"fields(first": ITEM_FIELDS, BOARD_READ: BoardServer(BOARD)})
    with pytest.raises(GitHubOperationError, match="#739 is not on the board"):
        store.set_field(board_item(739, card_id=CARD_737), ItemField.STATUS, "Ready")
    assert runner.writes == []


def test_clearing_a_field_sends_clear_and_records_null() -> None:
    store, runner = board_store(
        {"fields(first": ITEM_FIELDS, BOARD_READ: BoardServer(BOARD), "item-edit": ""}
    )
    store.set_field(board_item(737), ItemField.EFFORT, None)
    assert [args[7:] for args in runner.writes] == [
        [JOB_RECORD_ID, "--text", '{"Effort": null}'],
        [FIELD_IDS["Effort"], "--clear"],
    ]


def test_a_board_without_a_job_record_field_raises_before_any_write() -> None:
    store, runner = board_store({"fields(first": graphql_fields(FIELDS)})
    with pytest.raises(GitHubOperationError, match="Job record"):
        store.set_field(board_item(737), ItemField.PRIORITY, "P2-Medium")
    assert (runner.writes, graphql_kinds(runner)) == ([], ["fields"])


def _read_board_and_fields(replies: dict[str, Any]) -> tuple[GitHubRoadmapStore, RecordedGh]:
    """A store that has read the board, its issues and its fields, with one mark on #737, its
    calls then cleared."""
    store, runner = board_store(
        {
            "fields(first": ITEM_FIELDS,
            "issues?state=all": ISSUES_IN_MILESTONE,
            "item-edit": "",
            **replies,
        }
    )
    (item,) = store.items()
    store.set_marks(item, {RefineRecordKey.BODY_HASH: "b0"})
    runner.calls.clear()
    return store, runner


def test_a_value_write_sends_one_card_read_and_two_id_addressed_edits_and_no_board_read() -> None:
    """Once the store has read the board and its fields, a write reads only its card: no
    `field-list`, no budget probe, no board page, and no edit that names a card by URL or a
    field by name, which gh resolves by reading the board's first 100 items (#1361)."""
    store, runner = _read_board_and_fields({BOARD_READ: BoardServer(BOARD)})
    store.set_field(board_item(737), ItemField.VALUE, "High")
    assert (
        graphql_kinds(runner),
        [args for args, _ in runner.calls if "--url" in args or "--field" in args],
    ) == (["RoadmapBoardCard", "item-edit by id", "item-edit by id"], [])


def test_a_write_to_a_card_another_process_archived_raises_before_any_edit() -> None:
    board = on_board()
    store, runner = _read_board_and_fields({BOARD_READ: BoardServer(board)})
    board["items"][0]["isArchived"] = True
    with pytest.raises(GitHubOperationError, match="#737 is not on the board"):
        store.set_field(board_item(737), ItemField.VALUE, "High")
    assert (runner.writes, graphql_kinds(runner)) == ([], ["RoadmapBoardCard"])


def test_a_mark_another_process_wrote_after_the_listing_was_read_is_kept() -> None:
    """The record a write joins is the one the card holds when it is written, not the one the
    listing held (ADR 0002's last-set compare)."""
    board = on_board()
    store, runner = _read_board_and_fields({BOARD_READ: BoardServer(board)})
    (item,) = store.items()
    board["items"][0]["job record"] = '{"refine.failed_body_hash": "f1"}'
    store.set_marks(item, {RefineRecordKey.BODY_HASH: "b1"})
    assert json.loads(runner.writes[-1][-1]) == {
        "refine.body_hash": "b1",
        "refine.failed_body_hash": "f1",
    }


def test_two_stores_marking_one_card_at_once_keep_each_others_marks() -> None:
    """The Service's lanes each open a store for the repository, so two mark writes on one card
    can overlap: the later write joins the record the earlier one wrote, never the one both
    read before either wrote (#1532)."""
    github = GitHubFake(REPO)
    github.seed_issue(7, card={})
    armed, read, writing, written = (threading.Event() for _ in range(4))
    handoffs: list[bool] = []

    def held_after_its_card_read(
        args: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        answer = github(args, **kwargs)
        if armed.is_set() and BOARD_CARD_OPERATION in " ".join(args) and not read.is_set():
            read.set()
            # Held between its card read and its write: the other store's write lands here
            # unless the store keeps it out until this one writes. This short window checks
            # that it does not land, and opens only once the other store is about to write, so
            # it times the store's lock, not a thread start-up.
            handoffs.append(writing.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))
            written.wait(timeout=0.3)
        return answer

    first_store = GitHubRoadmapStore(
        REPO,
        board_owner="dan-petty",
        board_number=2,
        runner=held_after_its_card_read,
        session=RunnerSession(held_after_its_card_read),
    )
    second_store = GitHubRoadmapStore(
        REPO, board_owner="dan-petty", board_number=2, runner=github, session=RunnerSession(github)
    )
    (first_read,) = first_store.items()
    (second_read,) = second_store.items()

    def mark() -> None:
        handoffs.append(read.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))
        writing.set()
        second_store.set_marks(second_read, {RefineRecordKey.BODY_HASH: "b1"})
        written.set()

    marking = threading.Thread(target=mark)
    armed.set()
    marking.start()
    first_store.set_marks(first_read, {RefineRecordKey.FAILED_BODY_HASH: "f1"})
    marking.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    assert (json.loads((github.card(7) or {})["job record"]), handoffs) == (
        {"refine.body_hash": "b1", "refine.failed_body_hash": "f1"},
        [True, True],
    )


def _person_edits_after_the_read(
    **card: str,
) -> tuple[GitHubFake, GitHubRoadmapStore, Item]:
    """A store that read #7 with `card`'s fields, after which a person set Priority P1-High."""
    github = GitHubFake(REPO)
    github.seed_issue(7, card=card)
    store = GitHubRoadmapStore(
        REPO, board_owner="dan-petty", board_number=2, runner=github, session=RunnerSession(github)
    )
    (item,) = store.items()
    (github.card(7) or {})["priority"] = "P1-High"
    return github, store, item


def _item_edits(github: GitHubFake, start: int) -> list[list[str]]:
    return [args for args in github.calls[start:] if args[:2] == ["project", "item-edit"]]


def test_a_field_a_person_changed_after_the_listing_was_read_raises_before_any_edit() -> None:
    """The store read the board, then a person set Priority: the job's Priority write, planned
    from the listing, raises before any edit and the person's value stays (ADR 0002)."""
    github, store, item = _person_edits_after_the_read(priority="P2-Medium")
    start = len(github.calls)
    with pytest.raises(RoadmapCardChangedError, match="#7's Priority") as raised:
        store.set_field(item, ItemField.PRIORITY, "P3-Low")
    assert (
        _item_edits(github, start),
        (github.card(7) or {})["priority"],
        {key: raised.value.details[key] for key in ("field", "read", "now")},
    ) == ([], "P1-High", {"field": "Priority", "read": "P2-Medium", "now": "P1-High"})


def test_a_persons_change_stays_caught_after_the_store_wrote_another_field_of_its_card() -> None:
    """A write that reads the card takes only its job record into the listing, so a person's
    Priority it saw while writing Effort still stops the Priority write that follows."""
    github, store, item = _person_edits_after_the_read(priority="P2-Medium")
    store.set_field(item, ItemField.EFFORT, "Low")
    start = len(github.calls)
    with pytest.raises(RoadmapCardChangedError):
        store.set_field(item, ItemField.PRIORITY, "P3-Low")
    assert (_item_edits(github, start), (github.card(7) or {})["effort"]) == ([], "Low")


def test_a_write_of_the_value_the_card_holds_now_goes_ahead() -> None:
    """Writing the value someone else already set reverts nothing: the board's own "Item
    added" workflow sets Status New on a new card, and intake writes the same New."""
    github, store, item = _person_edits_after_the_read()
    store.set_field(item, ItemField.PRIORITY, "P1-High")
    card = github.card(7) or {}
    assert (card["priority"], json.loads(card["job record"])) == (
        "P1-High",
        {"Priority": "P1-High"},
    )


def test_the_stores_own_write_is_the_value_its_next_write_of_that_field_compares() -> None:
    """A job writes a field twice from the Item it planned with: the second write compares the
    card with the first write's value."""
    github = GitHubFake(REPO)
    github.seed_issue(7, card={"priority": "P2-Medium"})
    store = GitHubRoadmapStore(
        REPO, board_owner="dan-petty", board_number=2, runner=github, session=RunnerSession(github)
    )
    (item,) = store.items()
    store.set_field(item, ItemField.PRIORITY, "P1-High")
    store.set_field(item, ItemField.PRIORITY, "P0-Critical")
    assert (github.card(7) or {})["priority"] == "P0-Critical"


def test_a_read_after_a_duplicate_close_in_the_same_store_shows_the_status_the_board_set() -> None:
    """A close lets the board's "Item closed" workflow set the card's Status to Done, so the
    store drops the listings it read: a later read through the same store shows Done, not the
    Status the store read before the close."""
    github = GitHubFake(REPO, milestones=[{"number": 43, "title": "Q4 hardening", "state": "open"}])
    github.seed_issue(7, "feat: a copy", milestone="Q4 hardening", card={"status": "In Review"})
    github.seed_issue(8, "feat: the original", milestone="Q4 hardening", card={"status": "Ready"})
    store = GitHubRoadmapStore(
        REPO, board_owner="dan-petty", board_number=2, runner=github, session=RunnerSession(github)
    )
    before = {item.number: item.status for item in store.items(milestone=43)}
    store.close_as_duplicate(7, 8, None)
    after = {item.number: item.status for item in store.items(milestone=43)}
    assert (before[7], after[7]) == ("In Review", "Done")


def test_a_write_refuses_before_it_starts_while_the_points_left_are_below_the_reserve() -> None:
    """The card read reports the points left; below the reserve the write never starts."""
    server = BoardServer(BOARD, remaining=DEFAULT_GH_GRAPHQL_BUDGET_FLOOR)
    store, runner = board_store({"fields(first": ITEM_FIELDS, BOARD_READ: server})
    with pytest.raises(GitHubRateLimitError, match="stopped before writing #737"):
        store.set_marks(board_item(737), {RefineRecordKey.BODY_HASH: "b1"})
    assert runner.writes == []


def test_the_store_reads_the_board_once_and_its_own_writes_keep_that_listing_current() -> None:
    """Every reader of one filter shares one listing per store; a write updates the card in it
    with the values it sent, so a later read of the same store sees them without a re-read."""
    board = on_board()
    store, runner = board_store(
        {
            "fields(first": ITEM_FIELDS,
            BOARD_READ: BoardServer(board),
            "issues?state=all": ISSUES_IN_MILESTONE,
            "item-edit": "",
            f"api repos/{REPO}/issues/737": ISSUES_IN_MILESTONE[2],
        }
    )
    (before,) = store.items()
    store.set_field(before, ItemField.VALUE, "Low")
    after = store.item(737)
    probes = [args for args in graphql_kinds(runner) if args == "RoadmapBoard"]
    assert (
        after is not None and (after.value, after.job_record),
        len(probes),
        [item.number for item in store.items()],
    ) == ((("Low", {ItemField.VALUE: "Low"})), 2, [737])


@pytest.mark.parametrize("size", [120, 1_080])
def test_a_job_record_mark_costs_three_graphql_points_whatever_the_boards_size(size: int) -> None:
    """The store's fields (once a run), the one card and one edit by node ids: 3 points on a
    board of 120 cards or of 1,080, board #2's size on 2026-10-08, where the same mark through
    `field-list`, a whole-board read and a name-addressed `item-edit` cost about 215 (#1361)."""
    github = GitHubFake(REPO)
    for number in range(1, size + 1):
        github.seed_issue(number, card={"status": "Ready"})
    store = GitHubRoadmapStore(
        REPO, board_owner="dan-petty", board_number=2, runner=github, session=RunnerSession(github)
    )
    item = board_item(7, card_id=github.card_id(7))
    store.set_marks(item, {RefineRecordKey.BODY_HASH: "b1"})
    card = github.card(7) or {}
    assert (github.points, json.loads(card["job record"])) == (3, {"refine.body_hash": "b1"})


def test_add_item_adds_the_issue_by_its_url_and_returns_the_card_it_added() -> None:
    """`item-add --format json` names the card; its fields come from one read of that card,
    never from the board listing, which may not show a new card for minutes (#1361)."""
    board = on_board(917)
    board["items"][-1]["status"] = "New"
    store, runner = board_store(
        {
            "item-add": {"id": "PVTI_917", "title": OPEN_ISSUES[1]["title"], "type": "Issue"},
            "issues/917": OPEN_ISSUES[1],
            BOARD_READ: BoardServer(board),
        }
    )
    added = store.add_item(917)
    assert (
        runner.writes,
        graphql_kinds(runner),
        (added.number, added.card_id, added.status, added.title, added.state),
    ) == (
        [
            [
                "project",
                "item-add",
                "2",
                "--owner",
                "dan-petty",
                "--url",
                f"{ISSUE_URL}/917",
                "--format",
                "json",
            ]
        ],
        ["item-add", "RoadmapBoardCard"],
        (917, "PVTI_917", "New", OPEN_ISSUES[1]["title"], GitHubState.OPEN),
    )


def test_adding_an_issue_already_on_the_board_returns_its_existing_card() -> None:
    """GitHub's add answers with the card the issue already has, so it keeps its fields."""
    store, _ = board_store(
        {
            "item-add": {"id": CARD_737, "type": "Issue"},
            "issues/737": ISSUES_IN_MILESTONE[2],
            BOARD_READ: BoardServer(BOARD),
        }
    )
    added = store.add_item(737)
    assert (added.card_id, added.status, added.priority) == (CARD_737, "Done", "P1-High")


def _archived_card(**card: str) -> tuple[GitHubFake, GitHubRoadmapStore]:
    """Open issue #7, whose card a person archived holding `card`'s fields, and a store over
    it; the board's listing leaves the card out, so #7 is a candidate."""
    github = GitHubFake(REPO)
    github.seed_issue(7, "feat: archived by a person", card=card)
    (github.card(7) or {})["isArchived"] = True
    return github, GitHubRoadmapStore(
        REPO, board_owner="dan-petty", board_number=2, runner=github, session=RunnerSession(github)
    )


def _project_commands(github: GitHubFake) -> list[list[str]]:
    return [args[1:] for args in github.calls if args[0] == "project"]


def test_adding_an_issue_whose_card_is_archived_restores_that_card_with_its_fields() -> None:
    """`item-add` names the archived card. The store reads it once, restores it with one
    `item-archive --undo` by its node id, and returns it with the fields it holds; a later store
    lists it, so the issue is no longer a candidate (#1403). Without the restore, every round
    raised "Board #2 does not hold card PVTI_7 that #7 was just added as."."""
    github, store = _archived_card(status="Ready", value="High")
    candidates = [candidate.number for candidate in store.candidates()]
    added = store.add_item(7)
    later = GitHubRoadmapStore(
        REPO, board_owner="dan-petty", board_number=2, runner=github, session=RunnerSession(github)
    )
    assert (
        candidates,
        _project_commands(github),
        sum("RoadmapBoardCard" in " ".join(args) for args in github.calls),
        (added.restored, added.card_id, added.status, added.value),
        [candidate.number for candidate in later.candidates()],
        [(item.number, item.status, item.value) for item in later.items()],
    ) == (
        [7],
        [
            [
                "item-add",
                "2",
                "--owner",
                "dan-petty",
                "--url",
                f"{ISSUE_URL}/7",
                "--format",
                "json",
            ],
            [
                "item-archive",
                "2",
                "--owner",
                "dan-petty",
                "--id",
                "PVTI_7",
                "--undo",
                "--format",
                "json",
            ],
        ],
        1,
        (True, "PVTI_7", "Ready", "High"),
        [],
        [(7, "Ready", "High")],
    )


def test_adding_an_issue_whose_card_is_on_the_board_restores_nothing() -> None:
    github = GitHubFake(REPO)
    github.seed_issue(7, card={"status": "Ready"})
    store = GitHubRoadmapStore(
        REPO, board_owner="dan-petty", board_number=2, runner=github, session=RunnerSession(github)
    )
    added = store.add_item(7)
    assert ([args[0] for args in _project_commands(github)], added.status, added.restored) == (
        ["item-add"],
        "Ready",
        False,
    )


def test_a_restore_that_answers_with_another_card_raises_before_any_edit() -> None:
    """Fail closed: the store returns the card it restored only when gh names that card."""
    github, store = _archived_card(status="Ready")
    other = {"id": "PVTI_other", "title": "Issue 8", "type": "Issue"}
    with patch.object(github, "_unarchive", return_value=other):
        with pytest.raises(GitHubOperationError, match="answered with card PVTI_other"):
            store.add_item(7)
    assert [args[0] for args in _project_commands(github)] == ["item-add", "item-archive"]


def test_a_restore_refuses_while_the_card_read_leaves_fewer_points_than_the_reserve() -> None:
    """`item-add` is sent, and GitHub answers it with the card the issue has; the card read then
    reports fewer points than the reserve, so the restore is refused and the card stays
    archived."""
    github, store = _archived_card(status="Ready")
    github.board.remaining = DEFAULT_GH_GRAPHQL_BUDGET_FLOOR
    with pytest.raises(GitHubRateLimitError, match="stopped before writing #7"):
        store.add_item(7)
    assert (
        [args[0] for args in _project_commands(github)],
        (github.card(7) or {}).get("isArchived"),
    ) == (["item-add"], True)


def test_an_added_card_joins_the_listing_the_store_already_read() -> None:
    """A later read of the same store holds the card it added, though GitHub's listing may
    not list it yet."""
    board = on_board()
    added = deepcopy(board["items"][0])
    added.update(id="PVTI_917", content={**added["content"], "number": 917})
    server = BoardServer(board)

    def add(_: list[str]) -> dict[str, str]:
        board["items"].append(added)
        return {"id": "PVTI_917"}

    store, _ = board_store(
        {
            "item-add": add,
            "issues/917": OPEN_ISSUES[1],
            "issues?state=all": [*ISSUES_IN_MILESTONE, OPEN_ISSUES[1]],
            BOARD_READ: server,
        }
    )
    store.items()
    server.lagging["PVTI_917"] = 3
    store.add_item(917)
    assert ([item.number for item in store.items()], server.pages) == ([737, 917], 1)


def test_an_added_open_card_joins_the_open_items_listing_without_a_read() -> None:
    """Intake reads the open items for its candidates, then adds one: the open items' listing
    keeps the card the add returned, so the backlog shows it with no read that GitHub's lag
    could leave it out of."""
    github = GitHubFake(REPO, lag=3)
    github.seed_issue(5, "feat: new")
    store = GitHubRoadmapStore(
        REPO, board_owner="dan-petty", board_number=2, runner=github, session=RunnerSession(github)
    )
    before = [candidate.number for candidate in store.candidates()]
    start = len(github.calls)
    store.add_item(5)
    read_after = len(github.calls)
    assert (
        before,
        [candidate.number for candidate in store.candidates()],
        [item.number for item in store.backlog()],
        [args for args in github.calls[read_after:] if "RoadmapBoard" in " ".join(args)],
        github.board.lagging,
        start < read_after,
    ) == ([5], [], [5], [], {"PVTI_5": 3}, True)


def test_add_item_refuses_a_pull_request() -> None:
    store, runner = board_store({"issues/918": OPEN_ISSUES[0]})
    with pytest.raises(GitHubOperationError, match="pull request"):
        store.add_item(918)
    assert runner.writes == []


def test_item_reads_and_writes_raise_without_a_board() -> None:
    runner = RecordedGh({})
    store = GitHubRoadmapStore(REPO, runner=runner, session=RunnerSession(runner))
    with pytest.raises(GitHubOperationError, match="No board"):
        store.items()
    with pytest.raises(GitHubOperationError, match="No board"):
        store.add_item(917)
    assert runner.calls == []


# ── Failed reads ──────────────────────────────────────────────────────────────


def over_github(replies: dict[str, Any] | None = None) -> tuple[GitHubRoadmapStore, RecordedGh]:
    """The store whose REST listings the process's GitHub session reads from the `github_api`
    fake, and whose gh commands `replies` answer (#983)."""
    runner = RecordedGh(replies or {})
    store = GitHubRoadmapStore(
        REPO, board_owner="dan-petty", board_number=2, runner=runner, session=get_github_session()
    )
    return store, runner


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
    with pytest.raises(GitHubRateLimitError):
        store.milestones()


_SECONDARY = "gh: You have exceeded a secondary rate limit. (HTTP 403)"
# `gh api rate_limit` would report 4,900 GraphQL points while GraphQL's own budget answers 0,
# as #1125 measured: the store asks GraphQL.
_REST_SAYS_POINTS_LEFT = {
    "resources": {"graphql": {"limit": 5000, "remaining": 4900, "used": 100, "reset": 1}}
}


@pytest.mark.parametrize(
    ("budget", "error"),
    [
        pytest.param(budget_reply(4000), GitHubOperationError, id="points-left"),
        pytest.param(budget_reply(0), GitHubRateLimitError, id="quota-spent"),
        pytest.param((1, _SECONDARY), GitHubRateLimitError, id="budget-read-rate-limited"),
        pytest.param((1, "gh: Server Error (HTTP 502)"), GitHubRateLimitError, id="budget-unread"),
        pytest.param(
            (1, "gh: Bad credentials (HTTP 401)"), GitHubUnauthenticatedError, id="token-refused"
        ),
    ],
)
def test_an_owner_lookup_gh_drops_is_decided_by_graphqls_own_budget(
    budget: Any, error: type[GitHubOperationError]
) -> None:
    """gh project writes "unknown owner type" for any failed owner lookup, a 401, a 5xx, a SAML
    refusal or a rate limit alike, and drops the cause. The store's `--owner <login>` commands
    have no `@me` fallback, so it asks GraphQL for its own budget (#983, #1125): points left
    make a plain failure, which names them and still allows a secondary limit; a spent budget,
    or a budget read refused for a rate limit or unread, keeps the rate limit, which stops an
    intake round; a refused token is the unauthenticated error naming the failed command. REST's
    `gh api rate_limit`, which can report points GraphQL has not, is never read."""
    store, runner = board_store(
        {
            "item-add": (1, "unknown owner type"),
            "issues/917": OPEN_ISSUES[1],
            GRAPHQL_BUDGET_OPERATION: budget,
            "rate_limit": _REST_SAYS_POINTS_LEFT,
        }
    )
    with pytest.raises(GitHubOperationError) as raised:
        store.add_item(917)
    sent = [" ".join(args) for args, _ in runner.calls]
    assert (
        type(raised.value),
        GRAPHQL_BUDGET_OPERATION in sent[-1],
        any("rate_limit" in command for command in sent),
        # A kept rate limit is the classifier's own, naming gh's "unknown owner type".
        ("Could not add #917 to the board" if error is not GitHubRateLimitError else "unknown")
        in raised.value.message,
        ("4000 points left" in raised.value.message, "secondary" in raised.value.message)
        == ((True, True) if error is GitHubOperationError else (False, False)),
    ) == (error, True, False, True, True)


def _owner_lookup_through_run_gh(budget: tuple[int, str, str]) -> Callable[..., Any]:
    """gh at its process edge: the issue reads, `item-add` drops its owner lookup, and the
    GraphQL budget read exits with `budget`'s status, stdout and stderr."""

    def gh(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        command = " ".join(cmd)
        if "item-add" in command:
            return subprocess.CompletedProcess(cmd, 1, "", "unknown owner type")
        if GRAPHQL_BUDGET_OPERATION in command:
            return subprocess.CompletedProcess(cmd, *budget)
        return subprocess.CompletedProcess(cmd, 0, json.dumps(OPEN_ISSUES[1]), "")

    return gh


@pytest.mark.parametrize(
    ("budget", "error"),
    [
        pytest.param(
            (1, json.dumps({"message": "Server Error"}), "gh: Server Error (HTTP 502)"),
            GitHubRateLimitError,
            id="502",
        ),
        pytest.param(
            (1, "<html>upstream</html>", "gh: HTTP 504"), GitHubRateLimitError, id="html-504"
        ),
        pytest.param(
            (1, json.dumps({"message": "Bad credentials"}), "gh: Bad credentials (HTTP 401)"),
            GitHubUnauthenticatedError,
            id="401",
        ),
    ],
)
def test_through_run_gh_a_failed_budget_read_after_an_owner_lookup_is_classified(
    budget: tuple[int, str, str], error: type[GitHubOperationError]
) -> None:
    """Through the real `run_gh` with gh's process stubbed: a budget read gh fails, with
    GitHub's body on stdout, keeps the owner lookup's rate limit, naming gh's "unknown owner
    type" and the write, or, for a refused token, is the unauthenticated error naming the
    failed command; neither is replaced by an error about the read's own answer."""
    store = GitHubRoadmapStore(REPO, board_owner="dan-petty", board_number=2)
    with (
        patch(
            "devops_cli.github.rate_limiter._burst_protected_subprocess",
            side_effect=_owner_lookup_through_run_gh(budget),
        ),
        patch.object(GitHubRateLimiter, "acquire", autospec=True, return_value=0.0),
        pytest.raises(GitHubOperationError) as raised,
    ):
        store.add_item(917)
    details = raised.value.details
    assert (
        type(raised.value),
        details["operation"],
        details.get("output") if error is GitHubRateLimitError else "unknown owner type",
        ("Could not add #917 to the board" if error is not GitHubRateLimitError else "unknown")
        in raised.value.message,
    ) == (error, "roadmap.write", "unknown owner type", True)


def test_a_failed_gh_read_raises_and_names_the_read() -> None:
    store, _ = board_store({"contents/notes.md": (1, "HTTP 502: Bad Gateway")})
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
    store, _ = board_store({"contents/notes.md": (1, said)})
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

    store = GitHubRoadmapStore(REPO, board_owner="dan-petty", board_number=2, runner=gh)
    with pytest.raises(GitHubOperationError) as raised:
        store.repository_file("notes.md")
    assert (type(raised.value), "Could not read notes.md" in raised.value.message) == (
        GitHubOperationError,
        True,
    )


def test_a_listing_entry_that_is_not_the_shape_the_store_reads_raises() -> None:
    store, _ = board_store({"milestones?state=all": [{"number": 1}]})
    with pytest.raises(GitHubOperationError, match="malformed milestones"):
        store.milestones()


def test_an_error_object_where_a_listing_belongs_raises() -> None:
    store, _ = board_store(
        {"issues?state=open": {"message": "Not Found"}, BOARD_READ: BoardServer(BOARD)}
    )
    with pytest.raises(GitHubUnreadError, match="not a JSON array"):
        store.candidates()


def test_a_board_listing_with_fewer_items_than_its_total_raises() -> None:
    store, _ = board_store({BOARD_READ: BoardServer({**BOARD, "totalCount": 676})})
    with pytest.raises(GitHubOperationError, match="Read 4 of 676"):
        store.backlog()


def test_a_failed_write_raises() -> None:
    """The job record goes first, so when its write fails the field is never written."""
    store, runner = board_store(
        {
            "fields(first": ITEM_FIELDS,
            BOARD_READ: BoardServer(BOARD),
            "item-edit": (1, "GraphQL: Could not resolve"),
        }
    )
    with pytest.raises(GitHubOperationError, match="Could not set Job record on #737"):
        store.set_field(board_item(737), ItemField.STATUS, "Ready")
    assert [args[7] for args in runner.writes] == [JOB_RECORD_ID]


# ── The run's spend (#1400) ───────────────────────────────────────────────────


def test_the_spend_reads_no_budget_until_the_store_sends_a_graphql_request() -> None:
    """A store that has sent only REST requests has no spend to report, so it reads no budget;
    once it reads the board, the spend is read from GraphQL's own budget, as the run's last
    request. Without the read, as after a refusal, it comes from the last budget the board read
    reported, and nothing is sent."""
    server = BoardServer(BOARD, remaining=4000)
    store, runner = board_store(
        {
            "milestones?state=all": MILESTONES,
            GRAPHQL_BUDGET_OPERATION: budget_reply(3990),
            BOARD_READ: server,
            "issues?milestone=none": [],
        }
    )
    store.milestones()
    rest_only = (store.graphql_spend(read=False), store.graphql_spend(), len(runner.calls))
    store.backlog()
    sent = len(runner.calls)
    held = store.graphql_spend(read=False)
    unsent = len(runner.calls) - sent
    spend = store.graphql_spend()
    last = gh_variables(runner.calls[-1][0])["query"]
    assert (
        rest_only,
        (unsent, held is not None and held.remaining == server.remaining),
        GRAPHQL_BUDGET_OPERATION in last,
        spend is not None,
    ) == ((None, None, 1), (0, True), True, True)


# ── Paging and caching ────────────────────────────────────────────────────────


def test_every_rest_listing_is_read_through_the_session_a_full_page_at_a_time() -> None:
    """Each REST listing is read through the GitHub session at a full page, which follows
    GitHub's links itself; none goes through gh (#983)."""
    store, runner = board_store(
        {
            "milestones?state=all": MILESTONES,
            BOARD_READ: BoardServer(BOARD),
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
    ) == ([1] * 5, [(["100"], [])] * 5, [])


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
    ("path", "full", "read"),
    LISTINGS,
    ids=["milestones", "issues", "comments"],
)
def test_a_listing_page_that_is_not_a_json_list_raises_naming_it(
    github_api: GitHubApiFake,
    path: str,
    full: Any,
    read: Callable[[GitHubRoadmapStore], object],
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
        read(store)
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
    github_api.route("GET", first, github_json([OPEN_ISSUES[1]] * 100, headers=next_page(second)))
    github_api.route("GET", second, github_json([OPEN_ISSUES[1]] * 100))
    store, _ = over_github()
    assert (len(store.issues()), len(github_api.sent)) == (200, 2)


def test_every_read_passes_use_cache_false() -> None:
    store, runner = board_store(
        {
            "milestones?state=all": MILESTONES,
            BOARD_READ: BoardServer(BOARD),
            "fields(first": graphql_fields(FIELDS),
            "issues?milestone=43": ISSUES_IN_MILESTONE,
            "issues/737": ISSUES_IN_MILESTONE[2],
            "issues?state=open": OPEN_ISSUES,
            "issues/events": EVENTS,
        }
    )
    store.items(milestone=43)
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
    store, _ = over_github({BOARD_READ: BoardServer(BOARD)})
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
    store, _ = over_github({BOARD_READ: BoardServer(BOARD)})
    store.changes_since(cutoff)
    assert [url for url in github_api.requested if "issues/events" in url] == [
        f"GET {API}{EVENTS_LISTING}"
    ]


def test_changes_since_keeps_label_and_state_events_only() -> None:
    """A milestone event is a person's planning and no job reads it, so the poll reports none."""
    closed = next(e for e in EVENTS if e["event"] == "closed" and "pull_request" not in e["issue"])
    reopened = {**closed, "event": "reopened", "created_at": "2026-10-02T01:00:00Z"}
    store, _ = board_store({"issues/events": [reopened, *EVENTS], BOARD_READ: BoardServer(BOARD)})
    changes = store.changes_since(datetime(2026, 10, 1))
    assert [(change.kind, change.number, change.actor, change.label) for change in changes] == [
        (ChangeKind.UNLABELED, 829, "dan-petty", "priority/p1-high"),
        (ChangeKind.CLOSED, 299, "dan-petty", None),
        (ChangeKind.LABELED, 917, "dan-petty", "priority/p3-low"),
        (ChangeKind.REOPENED, 299, "dan-petty", None),
    ]


def test_changes_since_drops_an_actors_own_changes_before_it_reads_the_board() -> None:
    """A run's own events read no job record, so a round whose events are all its own sends
    no GraphQL request (#1361); the others' changes still carry theirs."""
    closed = next(e for e in EVENTS if e["event"] == "closed" and "pull_request" not in e["issue"])
    own = {**closed, "actor": {"login": "roadmap-bot"}, "created_at": "2026-10-02T01:00:00Z"}
    store, runner = board_store({"issues/events": [own], BOARD_READ: BoardServer(BOARD)})
    alone = store.changes_since(datetime(2026, 10, 1, tzinfo=UTC), except_actor="roadmap-bot")
    sent_alone = graphql_kinds(runner)
    runner.replies["issues/events"] = [own, *EVENTS]
    mixed = store.changes_since(datetime(2026, 10, 1, tzinfo=UTC), except_actor="roadmap-bot")
    assert (alone, sent_alone, {change.actor for change in mixed}, len(mixed)) == (
        [],
        [],
        {"dan-petty"},
        3,
    )


def test_changes_since_with_an_empty_actor_leaves_out_nothing() -> None:
    """An empty session login names no actor, so no change is left out, not even one GitHub
    reports with an empty login."""
    closed = next(e for e in EVENTS if e["event"] == "closed" and "pull_request" not in e["issue"])
    nameless = {**closed, "actor": {"login": ""}, "created_at": "2026-10-02T01:00:00Z"}
    store, _ = board_store({"issues/events": [nameless], BOARD_READ: BoardServer(BOARD)})
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


def test_the_factory_opens_the_github_adapter_without_reading(
    github_roadmap_factory: Callable[..., RoadmapStore],
) -> None:
    store = github_roadmap_factory(REPO, board_owner="dan-petty", board_number=2)
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

    store = github_roadmap_factory(REPO, board_owner="dan-petty", board_number=2, runner=refuse)
    titles = [milestone.title for milestone in store.milestones()]
    assert (titles[0], github_api.requested) == (
        "2026-10-29",
        [f"GET {API}/{LISTING_MILESTONES}"],
    )


# ── Board fields, issues and files (#739) ─────────────────────────────────────
# The GraphQL replies follow the shape of GitHub's ProjectV2 schema; the option ids are the
# recorded board's (`project-field-list.json`).

STATUS_NODE = {
    "id": "PVTSSF_lAHOAHXnKc4BiwcgzhhnQg8",
    "name": "Status",
    "dataType": "SINGLE_SELECT",
    "options": [
        {"id": "5b8424c8", "name": "Todo", "color": "GRAY", "description": ""},
        {"id": "89415499", "name": "Ready", "color": "BLUE", "description": ""},
    ],
}
FIELD_NODES = [
    {"id": "PVTF_lAHOAHXnKc4BiwcgzhhnQg0", "name": "Title", "dataType": "TITLE"},
    STATUS_NODE,
    {"id": "PVTF_jobrecord", "name": "Job record", "dataType": "TEXT"},
]


def owned_board(selection: str, nodes: list[Any]) -> dict[str, Any]:
    connection = {"totalCount": len(nodes), "nodes": nodes}
    return {"data": {"repositoryOwner": {"projectV2": {"id": BOARD_ID, selection: connection}}}}


FIELDS_REPLY = owned_board("fields", FIELD_NODES)


def test_the_board_fields_come_from_graphql_once_and_a_write_sends_an_options_id() -> None:
    store, runner = board_store(
        {"fields(first": FIELDS_REPLY, BOARD_READ: BoardServer(BOARD), "item-edit": ""}
    )
    store.set_field(board_item(737), ItemField.STATUS, "Ready")
    store.set_field(board_item(737), ItemField.STATUS, "Todo")
    fields_reads = [args for args, _ in runner.calls if "fields(first" in " ".join(args)]
    assert (
        fields_reads[0][:3] + fields_reads[0][4:],
        len(fields_reads),
        [args[-1] for args in runner.writes if "--single-select-option-id" in args],
    ) == (
        ["api", "graphql", "-f", "-f", "owner=dan-petty", "-F", "number=2", "-F", "first=100"],
        1,
        ["89415499", "5b8424c8"],
    )


def test_a_short_field_listing_raises_before_any_write() -> None:
    reply = owned_board("fields", FIELD_NODES)
    reply["data"]["repositoryOwner"]["projectV2"]["fields"]["totalCount"] = 9
    store, runner = board_store({"fields(first": reply})
    with pytest.raises(GitHubOperationError, match="Read 3 of 9"):
        store.set_field(board_item(737), ItemField.STATUS, "Ready")
    assert runner.writes == []


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


def test_issues_read_every_state_and_drop_pull_requests() -> None:
    store, runner = board_store({"issues?state=all": ISSUES_IN_MILESTONE + OPEN_ISSUES})
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
    store, runner = board_store({"contents/": "board = 2\n"})
    texts = (
        store.repository_file(".github/roadmap.toml", ref="feat/topic"),
        store.repository_file(".github/roadmap.toml"),
    )
    assert (texts, [args for args, _ in runner.calls]) == (
        ("board = 2\n", "board = 2\n"),
        [
            [
                "api",
                "-H",
                "Accept: application/vnd.github.raw+json",
                f"repos/{REPO}/contents/.github/roadmap.toml?ref=feat%2Ftopic",
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
    with pytest.raises(GitHubFileNotFoundError, match=r"has no \.github/labels\.yml at main"):
        missing.repository_file(".github/labels.yml", ref="main")
    with pytest.raises(
        GitHubOperationError, match=r"Could not read \.github/labels\.yml"
    ) as failed:
        broken.repository_file(".github/labels.yml", ref="main")
    assert isinstance(failed.value, GitHubFileNotFoundError) is False


# ── Comments and marks ────────────────────────────────────────────────────────


def test_comments_on_reads_every_comment_of_the_issue_oldest_first() -> None:
    store, runner = board_store({"issues/844/comments": recorded("issue-844-comments.json")})
    (comment,) = store.comments_on(844)
    assert (
        comment.startswith("**Placement (2026-10-02):** moved from v0.2.28"),
        runner.calls[0][0],
    ) == (
        True,
        [f"{API}/repos/{REPO}/issues/844/comments?per_page=100"],
    )


def test_comment_posts_one_comment() -> None:
    store, runner = board_store({"-X POST": {}})
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


def test_set_marks_merges_the_marks_into_the_job_record_the_card_holds_in_one_write() -> None:
    board = on_board()
    board["items"][0]["job record"] = '{"Status": "Ready", "refine.body_hash": "b0"}'
    store, runner = board_store(
        {"fields(first": ITEM_FIELDS, BOARD_READ: BoardServer(board), "item-edit": ""}
    )
    store.set_marks(
        board_item(737), {RefineRecordKey.SECTION_HASH: "s1", RefineRecordKey.BODY_HASH: None}
    )
    assert [(args[7:9], json.loads(args[-1])) for args in runner.writes] == [
        (
            [JOB_RECORD_ID, "--text"],
            {"Status": "Ready", "refine.body_hash": None, "refine.section_hash": "s1"},
        )
    ]


def test_every_job_record_write_keeps_the_keys_this_version_does_not_know() -> None:
    """Another version's key survives this version's writes: none rebuilds the record from only
    the keys it read."""
    board = on_board()
    board["items"][0]["job record"] = '{"OtherTool": "x", "OtherFlag": "yes"}'
    store, runner = board_store(
        {"fields(first": ITEM_FIELDS, BOARD_READ: BoardServer(board), "item-edit": ""}
    )
    store.set_marks(board_item(737), {RefineRecordKey.BODY_HASH: "b1"})
    store.set_field(board_item(737), ItemField.PRIORITY, "P1-High")
    assert [json.loads(args[-1]) for args in runner.writes if args[-2] == "--text"] == [
        {"OtherTool": "x", "OtherFlag": "yes", "refine.body_hash": "b1"},
        {"OtherTool": "x", "OtherFlag": "yes", "Priority": "P1-High"},
    ]


def test_set_marks_raises_before_any_write_for_an_item_off_the_board() -> None:
    store, runner = board_store({"fields(first": ITEM_FIELDS, BOARD_READ: BoardServer(BOARD)})
    with pytest.raises(GitHubOperationError, match="#739 is not on the board"):
        store.set_marks(board_item(739), {RefineRecordKey.BODY_HASH: "b1"})
    assert runner.writes == []


def test_an_item_no_store_read_has_no_card_to_write_and_raises_before_any_write() -> None:
    """An Item built as a probe, not read from a store, carries no card id."""
    store, runner = board_store({"fields(first": ITEM_FIELDS})
    probe = Item(number=737, title="#737", url=f"{ISSUE_URL}/737")
    with pytest.raises(GitHubOperationError, match="#737 is not on the board"):
        store.set_marks(probe, {RefineRecordKey.BODY_HASH: "b1"})
    assert (runner.writes, graphql_kinds(runner)) == ([], ["fields"])


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
    nodes: list[dict[str, Any]] = [
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


def test_issue_records_and_milestones_carry_author_and_close_times() -> None:
    closed = {**MILESTONES[0], "state": "closed", "closed_at": "2026-10-03T20:37:25Z"}
    store, _ = board_store(
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
