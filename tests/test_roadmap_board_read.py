"""The roadmap store's paged, filtered GraphQL board reads and the points they spend (#1125).

The board is served by `BoardServer`, which answers the store's queries as GraphQL would. The
query documents are validated against the part of GitHub's public schema they use
(`tests/fixtures/roadmap/github-schema-board.graphql`). No case starts `gh`, opens a socket or
sleeps.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from graphql import build_schema, parse, validate

from devops_cli.config.defaults import DEFAULT_GH_GRAPHQL_BUDGET_FLOOR
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.github.rate_limiter import get_github_rate_limiter, reset_github_rate_limiter
from devops_cli.roadmap.board_read import (
    BOARD_BUDGET_QUERY,
    BOARD_ITEMS_QUERY,
    GRAPHQL_BUDGET_QUERY,
    GraphQLBudget,
    GraphQLSpend,
    board_budget_args,
    board_items_args,
    graphql_budget_args,
    spend_between,
)
from devops_cli.roadmap.config import RoadmapConfig
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.roadmap.reprioritize import plan_reprioritization
from tests.roadmap_board_fake import BOARD_READ, BoardServer, budget_reply, gh_variables

REPO = "dan-petty/devops-cli"
OWNER = "dan-petty"
SCHEMA = Path(__file__).parent / "fixtures" / "roadmap" / "github-schema-board.graphql"
NOW = datetime(2026, 10, 4, tzinfo=UTC)
# A quota far from spent and far from its reset, so `run_gh`'s pacing never waits on it.
QUOTA = {"limit": 5000, "remaining": 5000, "used": 0, "reset": 4_000_000_000}


def board_of(open_items: int, closed_items: int, *, archived: int = 0) -> dict[str, Any]:
    """A board of this repository's issues #1..: the open ones first, then the closed ones,
    then `archived` closed ones that are archived."""
    items = []
    for number in range(1, open_items + closed_items + archived + 1):
        is_open = number <= open_items
        items.append(
            {
                "id": f"PVTI_{number}",
                "content": {
                    "type": "Issue",
                    "number": number,
                    "repository": REPO,
                    "title": f"#{number}",
                    "url": f"https://github.com/{REPO}/issues/{number}",
                    "state": "OPEN" if is_open else "CLOSED",
                },
                "status": "Ready" if is_open else "Done",
                **({"isArchived": True} if number > open_items + closed_items else {}),
            }
        )
    return {"items": items, "totalCount": len(items)}


def issues_of(board: dict[str, Any]) -> list[dict[str, Any]]:
    """The REST issues of every item on `board`."""
    return [
        {
            "number": entry["content"]["number"],
            "title": entry["content"]["title"],
            "html_url": entry["content"]["url"],
            "state": entry["content"]["state"].lower(),
            "labels": [],
            "milestone": None,
        }
        for entry in board["items"]
    ]


class Gh:
    """Answers each command by the first key its argv contains; keeps every argv."""

    def __init__(self, replies: dict[str, Any]) -> None:
        self.replies = replies
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        command = " ".join(args)
        key = next((key for key in self.replies if key in command), None)
        assert key is not None, f"no reply for: {command[:200]}"
        reply = self.replies[key]
        reply = reply(args) if callable(reply) else reply
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return subprocess.CompletedProcess(args, 0, text, "")


def store_over(replies: dict[str, Any]) -> tuple[GitHubRoadmapStore, Gh]:
    gh = Gh(replies)
    return GitHubRoadmapStore(REPO, board_owner=OWNER, board_number=2, runner=gh), gh


def board_reads(gh: Gh) -> list[dict[str, str]]:
    """The variables of every board query the store sent, in order."""
    return [gh_variables(args) for args in gh.calls if "RoadmapBoard" in " ".join(args)]


# ── The documents ─────────────────────────────────────────────────────────────


def test_every_board_document_is_valid_against_githubs_schema() -> None:
    """The documents are fixed templates; GitHub's schema, cut to the types they use, accepts
    each of them and rejects a field it doesn't define."""
    schema = build_schema(SCHEMA.read_text(encoding="utf-8"))
    documents = [BOARD_ITEMS_QUERY, BOARD_BUDGET_QUERY, GRAPHQL_BUDGET_QUERY]
    misspelled = BOARD_ITEMS_QUERY.replace("archivedStates", "archived")
    assert (
        [validate(schema, parse(document)) for document in documents],
        len(validate(schema, parse(misspelled))),
    ) == ([[], [], []], 1)


def test_the_argument_builders_send_the_filter_the_cursor_and_typed_numbers() -> None:
    """A request plan lists these same argv; the filter goes as a string, the numbers typed."""
    first = board_items_args(OWNER, 2, "is:open")
    later = board_items_args(OWNER, 2, "", after="Y3Vyc29y")
    assert (
        first[:3],
        {key: value for key, value in gh_variables(first).items() if key != "query"},
        gh_variables(later)["after"],
        gh_variables(later)["filter"],
        "archivedStates: [NOT_ARCHIVED]" in gh_variables(first)["query"],
        gh_variables(board_budget_args(OWNER, 2, "is:open"))["filter"],
        graphql_budget_args()[:3],
    ) == (
        ["api", "graphql", "-f"],
        {"owner": OWNER, "filter": "is:open", "number": "2", "first": "100", "fieldValues": "100"},
        "Y3Vyc29y",
        "",
        True,
        "is:open",
        ["api", "graphql", "-f"],
    )


# ── Filters and counts ────────────────────────────────────────────────────────


def test_each_read_passes_its_filter_at_the_source() -> None:
    """The job's filter for its whole-board reads, `is:open` for the backlog and candidates."""
    board = board_of(3, 2)
    store, gh = store_over(
        {
            BOARD_READ: BoardServer(board),
            "issues?milestone=none": issues_of(board)[:3],
            "issues?state=open": issues_of(board)[:3],
            "issues?state=all": issues_of(board),
        }
    )
    reprioritize = GitHubRoadmapStore(
        REPO, board_owner=OWNER, board_number=2, runner=gh, board_filter="-status:Done"
    )
    store.items()
    store.backlog()
    store.candidates()
    reprioritize.cards()
    assert [read["filter"] for read in board_reads(gh)] == [
        "",
        "",
        "is:open",
        "is:open",
        "is:open",
        "is:open",
        "-status:Done",
        "-status:Done",
    ]


def test_an_archived_item_never_fails_the_read() -> None:
    """The total is the same filter's, archived items left out of both (2026-10-04: one archived
    item stopped migrate with "Read 930 of 931")."""
    board = board_of(2, 2, archived=1)
    store, _ = store_over({BOARD_READ: BoardServer(board), "issues?state=all": issues_of(board)})
    assert [item.number for item in store.items()] == [1, 2, 3, 4]


def test_a_count_that_changes_during_the_read_is_read_again_once() -> None:
    """An item added after the first page is caught by the next page's total; the second read
    sees a still board and succeeds."""
    board = board_of(150, 0)
    extra = board_of(151, 0)["items"][-1]

    def add_one(server: BoardServer, page: int) -> None:
        if page == 1:
            server.listing["items"].append(extra)

    server = BoardServer(board, on_page=add_one)
    store, gh = store_over({BOARD_READ: server})
    cards = store.cards()
    assert (len(cards), server.pages, len(board_reads(gh))) == (151, 4, 5)


def test_a_count_that_changes_on_both_reads_fails_closed() -> None:
    board = board_of(150, 0)

    def add_one(server: BoardServer, page: int) -> None:
        if page in (1, 3):
            server.listing["items"].append(board_of(150 + page, 0)["items"][-1])

    store, _ = store_over({BOARD_READ: BoardServer(board, on_page=add_one)})
    with pytest.raises(GitHubOperationError, match="changed while they were read") as raised:
        store.cards()
    assert "150, 151, 151, 152; received 152" in str(raised.value)


# ── The budget ────────────────────────────────────────────────────────────────


def test_a_read_below_the_floor_is_refused_before_any_page() -> None:
    """With the floor plus the read's cost not left, the run stops after the one small query
    that reads the budget, and reads no page."""
    board = board_of(280, 651)
    server = BoardServer(board, remaining=DEFAULT_GH_GRAPHQL_BUDGET_FLOOR + 10)
    store, gh = store_over({BOARD_READ: server})
    with pytest.raises(GitHubRateLimitError, match="stopped before reading and spent nothing"):
        store.cards()
    assert (server.pages, server.spent, len(gh.calls)) == (0, 1, 1)


def test_a_read_stops_before_a_page_once_below_the_floor() -> None:
    """A page that costs more than the read was taken to cost leaves the budget under the
    floor: the next page is not read."""
    server = BoardServer(
        board_of(300, 0), remaining=DEFAULT_GH_GRAPHQL_BUDGET_FLOOR + 50, page_cost=100
    )
    store, _ = store_over({BOARD_READ: server})
    with pytest.raises(GitHubRateLimitError, match="stopped before page 2"):
        store.cards()
    assert (server.pages, server.remaining) == (1, DEFAULT_GH_GRAPHQL_BUDGET_FLOOR - 51)


# ── A reprioritize run ────────────────────────────────────────────────────────


def _fields_reply() -> dict[str, Any]:
    status = {
        "id": "PVTSSF_status",
        "name": "Status",
        "dataType": "SINGLE_SELECT",
        "options": [
            {"id": f"o{i}", "name": name}
            for i, name in enumerate(("New", "Ready", "Blocked", "Done"))
        ],
    }
    record = {"id": "PVTF_jobrecord", "name": "Job record", "dataType": "TEXT"}
    connection = {"totalCount": 2, "nodes": [status, record]}
    return {"data": {"repositoryOwner": {"projectV2": {"fields": connection}}}}


def _rest_pages(listing: list[dict[str, Any]]) -> Callable[[list[str]], Any]:
    def page(args: list[str]) -> Any:
        (number,) = parse_qs(urlsplit(args[-1]).query)["page"]
        start = (int(number) - 1) * 100
        return listing[start : start + 100]

    return page


def test_a_reprioritize_run_on_a_board_of_931_items_charges_its_pages() -> None:
    """The board of 2026-10-04: 931 items, 280 of them open, one more archived. Through `run_gh`,
    with gh's process stubbed, the run charges the GraphQL points its board reads report: two
    reads (the items, then the run record), each one budget query and ten pages of 100. The
    same run through `gh project item-list` cost 2,025 points while the limiter counted one call
    per read. The run ends with the points spent and left, read from GraphQL."""
    board = board_of(280, 651, archived=1)
    server = BoardServer(board)
    gh = Gh(
        {
            "fields(first": _fields_reply(),
            BOARD_READ: server,
            "issues?state=all": _rest_pages(issues_of(board)),
            "milestones?state=all": [],
            "defaultBranchRef": {
                "data": {
                    "repository": {
                        "defaultBranchRef": {"name": "main", "target": {"oid": "a" * 40}}
                    }
                }
            },
            "RoadmapGraphQLBudget": lambda _: budget_reply(server.remaining - 1),
            "rate_limit": {"resources": {"core": QUOTA, "graphql": QUOTA}},
        }
    )
    reset_github_rate_limiter()
    try:
        with (
            patch(
                "devops_cli.github.rate_limiter._burst_protected_subprocess",
                side_effect=lambda cmd, **kw: gh(cmd[1:], **kw),
            ),
            patch(
                "devops_cli.github.rate_limiter.run_subprocess",
                side_effect=lambda cmd, **kw: gh(cmd[1:], **kw),
            ),
            patch("devops_cli.github.rate_limiter.time.sleep"),
        ):
            store = GitHubRoadmapStore(REPO, board_owner=OWNER, board_number=2)
            plan = plan_reprioritization(store, repo=REPO, config=RoadmapConfig(board=2), now=NOW)
            spend = store.graphql_spend()
            charged = get_github_rate_limiter().points_charged("graphql")
    finally:
        reset_github_rate_limiter()
    reads = board_reads(gh)
    assert (
        plan.current,
        [read["filter"] for read in reads],
        server.pages,
        charged,
        (spend.spent, spend.remaining),
    ) == (None, [""] * 22, 20, 23, (23, 4977))


# ── The spend line ────────────────────────────────────────────────────────────


class _Spending:
    def __init__(self, spend: GraphQLSpend | None | Exception) -> None:
        self.spend = spend

    def graphql_spend(self) -> GraphQLSpend | None:
        if isinstance(self.spend, Exception):
            raise self.spend
        return self.spend


def test_a_run_ends_with_one_line_of_graphql_points_spent_and_left_however_it_ends() -> None:
    """A run that finishes, and one that fails, each end with the line; a store that spends no
    points (the in-memory one) prints none, and a budget that can't be read prints none."""
    from devops_cli.commands.roadmap import _reporting_spend

    spend = GraphQLSpend(spent=23, remaining=4977, reset_at=datetime(2026, 10, 4, 13, tzinfo=UTC))
    printed: list[str] = []
    with patch("devops_cli.commands.roadmap.print_info", side_effect=printed.append):
        with _reporting_spend([_Spending(spend)]):  # type: ignore[list-item]
            pass
        with pytest.raises(GitHubOperationError), _reporting_spend([_Spending(spend)]):  # type: ignore[list-item]
            raise GitHubOperationError("read failed")
        with _reporting_spend([_Spending(None), _Spending(GitHubOperationError("down"))]):  # type: ignore[list-item]
            pass
    assert printed == ["GraphQL: 23 points spent, 4977 left until 13:00 UTC."] * 2


def test_a_run_the_hourly_reset_crossed_counts_what_it_spent_since_the_reset() -> None:
    first = GraphQLBudget(cost=1, limit=5000, remaining=40, used=4960, reset_at=NOW)
    later = GraphQLBudget(
        cost=1, limit=5000, remaining=4990, used=10, reset_at=datetime(2026, 10, 4, 1, tzinfo=UTC)
    )
    same = GraphQLBudget(cost=1, limit=5000, remaining=20, used=4980, reset_at=NOW)
    assert (
        spend_between(first, same).spent,
        spend_between(first, later).line(),
    ) == (
        21,
        "GraphQL: 10 points spent since the hourly reset during the run, 4990 left until 01:00 UTC.",
    )
