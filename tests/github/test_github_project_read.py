"""The paged GraphQL board reads of `devops gh project` and the budget they keep (#1125).

The query documents are validated against the part of GitHub's public schema they use
(`tests/fixtures/roadmap/github-schema-board.graphql`). The reads themselves run through
`devops gh project reconcile`, whose tests are `tests/test_github_projects.py` and
`tests/test_github_projects_reconcile.py`. No roadmap job reads a board (ADR 0016). No case starts
`gh`, opens a socket or sleeps.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from graphql import build_schema, parse, validate

from devops_cli.config.defaults import DEFAULT_GH_GRAPHQL_BUDGET_FLOOR
from devops_cli.exceptions.git import GitHubRateLimitError
from devops_cli.github.project_read import (
    BOARD_BUDGET_QUERY,
    BOARD_ITEMS_QUERY,
    GRAPHQL_BUDGET_QUERY,
    BoardItemsPage,
    GraphQLBudget,
    board_budget_args,
    board_items_args,
    field_list_args,
    graphql_budget_args,
    item_edit_args,
    read_cost,
    require_budget,
    require_floor,
)
from tests.project_board_fake import BoardServer, gh_variables
from tests.support.paths import FIXTURES

OWNER = "dan-petty"
SCHEMA = FIXTURES / "roadmap" / "github-schema-board.graphql"
RESET = datetime(2026, 10, 8, 13, tzinfo=UTC)


def budget(left: int) -> GraphQLBudget:
    """A budget that GraphQL reports with `left` points left until `RESET`."""
    return GraphQLBudget(cost=1, limit=5000, remaining=left, used=5000 - left, reset_at=RESET)


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


def test_the_project_commands_reconcile_sends_name_the_board_and_the_field() -> None:
    """`gh project field-list` and `gh project item-edit` by name, as reconcile sends them."""
    url = "https://github.com/o/r/issues/7"
    assert (
        field_list_args(OWNER, 2),
        item_edit_args(OWNER, 2, url, "Status", ["--value", "Ready"]),
    ) == (
        ["project", "field-list", "2", "--owner", OWNER, "--format", "json", "--limit", "100"],
        [
            "project",
            "item-edit",
            "2",
            "--owner",
            OWNER,
            "--url",
            url,
            "--field",
            "Status",
            "--value",
            "Ready",
        ],
    )


def test_a_page_lists_its_items_as_gh_project_item_list_does_and_names_the_next_cursor() -> None:
    """A page's nodes take the shape `gh project item-list` gives, each field value under its
    name with the first letter lower-cased; the cursor names the next page while there is one."""
    listing = {
        "items": [
            {
                "id": "PVTI_7",
                "content": {"type": "Issue", "number": 7, "repository": "o/r"},
                "status": "Ready",
            },
            {"id": "PVTI_8", "content": {"type": "Issue", "number": 8, "repository": "o/r"}},
        ],
        "totalCount": 2,
    }
    first = BoardServer(listing)(
        ["-f", f"query={BOARD_ITEMS_QUERY}", "-f", "filter=", "-F", "first=1"]
    )
    page = BoardItemsPage.model_validate(first)
    assert (page.listed(), page.next_cursor()) == (
        [
            {
                "id": "PVTI_7",
                "content": {"type": "Issue", "number": 7, "repository": "o/r"},
                "status": "Ready",
            }
        ],
        "1",
    )


# ── The budget ────────────────────────────────────────────────────────────────


def test_a_read_costs_its_pages_and_at_least_one() -> None:
    assert [read_cost(total, 2) for total in (0, 100, 101, 931)] == [2, 2, 4, 20]


def test_each_refusal_carries_its_budgets_reset_in_its_details() -> None:
    """A refusal names the points left and the reset, ISO 8601, in its details (#1400)."""
    left = DEFAULT_GH_GRAPHQL_BUDGET_FLOOR - 1
    refusals: list[GitHubRateLimitError] = []
    for refuse in (
        lambda: require_budget(budget(left), 3, "board #2 items"),
        lambda: require_floor(budget(left), "board #2 items", 2),
    ):
        with pytest.raises(GitHubRateLimitError) as raised:
            refuse()
        refusals.append(raised.value)
    common = {"subcommand": "graphql", "remaining": left, "reset_at": RESET.isoformat()}
    assert [refusal.details for refusal in refusals] == [
        {"operation": "project.read", **common, "cost": 3},
        {"operation": "project.read", **common, "page": 2},
    ]


def test_a_read_that_leaves_the_floor_goes_ahead() -> None:
    """A read whose cost leaves exactly the floor, and a page read at the floor, are allowed."""
    floor = DEFAULT_GH_GRAPHQL_BUDGET_FLOOR
    require_budget(budget(floor + 3), 3, "board #2 items")
    require_floor(budget(floor), "board #2 items", 2)
    with pytest.raises(GitHubRateLimitError, match="stopped before reading and spent nothing"):
        require_budget(budget(floor + 2), 3, "board #2 items")
