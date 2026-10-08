"""Paged, filtered GraphQL reads of a roadmap board, and the GraphQL points they spend (#1125).

`gh project item-list` pages the board itself with queries that ask for every field of every
item, filters nothing, and reports no cost, so one read spent about 2,000 of GraphQL's 5,000
hourly points while the rate limiter counted one call. The store reads the board with its own
query instead, a page of `DEFAULT_GH_PROJECT_ITEM_PAGE_SIZE` items at a time, each page asking
for the item fields the store keeps and for `rateLimit`, so `run_gh` charges the points GitHub
reports. Every read passes the reading job's Projects filter as `items(query:)` and leaves
archived items out (`archivedStates: [NOT_ARCHIVED]`); the total it checks the read against is
the same connection's `totalCount`, so it counts the same items.

Before the pages, one small query (`RoadmapBoardBudget`) reads the points left and the filter's
total; a read that would leave fewer than `DEFAULT_GH_GRAPHQL_BUDGET_FLOOR` points refuses there,
having spent nothing on pages, and a read stops before any page while fewer than the floor are
left.

A write reads only the card it writes (#1361): `RoadmapBoardCard` reads one item by its node id,
archived or not, with the same item fields a page holds and `rateLimit`, for about one point
whatever the board's size, and a write refuses before it starts while fewer than the floor are
left. A write leaves an archived card alone; the add that names an issue's archived card restores
it (#1403). The documents are fixed templates, validated against GitHub's public schema in a test.

Each refusal carries the budget's reset in its details (`CONST_GRAPHQL_REFUSAL_RESET_KEY`),
which the Service reads to hold every repository's rounds until then (#1400).

This module only builds `gh` arguments and reads payloads; the store runs them, so a request plan
can list the same argv the store sends.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from pydantic import AliasPath, BaseModel, ConfigDict, Field

from devops_cli.config.constants import CONST_GRAPHQL_REFUSAL_RESET_KEY
from devops_cli.config.defaults import (
    DEFAULT_GH_GRAPHQL_BUDGET_FLOOR,
    DEFAULT_GH_PROJECT_FIELD_LIMIT,
    DEFAULT_GH_PROJECT_ITEM_PAGE_SIZE,
)
from devops_cli.exceptions.git import GitHubRateLimitError
from devops_cli.lang import MESSAGES

BOARD_ITEMS_OPERATION = "RoadmapBoardItems"
BOARD_BUDGET_OPERATION = "RoadmapBoardBudget"
BOARD_CARD_OPERATION = "RoadmapBoardCard"
GRAPHQL_BUDGET_OPERATION = "RoadmapGraphQLBudget"

_RATE_LIMIT = "rateLimit { cost limit remaining used resetAt }"
_ITEMS = "items(first: {first}, {after}query: $filter, archivedStates: [NOT_ARCHIVED])"
_OWNED_BOARD = (
    "repositoryOwner(login: $owner) {{ ... on ProjectV2Owner {{ "
    "projectV2(number: $number) {{ {selection} }} }} }}"
)
_FIELD_NAME = "field { ... on ProjectV2FieldCommon { name } }"
_REPOSITORY_CONTENT = "number title url repository { nameWithOwner }"
# The item fields the store keeps, the same in a page and in a one-card read.
_ITEM_SELECTION = (
    "id content { __typename ... on DraftIssue { title } "
    f"... on Issue {{ {_REPOSITORY_CONTENT} }} "
    f"... on PullRequest {{ {_REPOSITORY_CONTENT} }} }} "
    "fieldValues(first: $fieldValues) { nodes { "
    f"... on ProjectV2ItemFieldSingleSelectValue {{ name {_FIELD_NAME} }} "
    f"... on ProjectV2ItemFieldTextValue {{ text {_FIELD_NAME} }} "
    f"... on ProjectV2ItemFieldDateValue {{ date {_FIELD_NAME} }} }} }}"
)

BOARD_ITEMS_QUERY = (
    f"query {BOARD_ITEMS_OPERATION}($owner: String!, $number: Int!, $filter: String!, "
    "$first: Int!, $after: String, $fieldValues: Int!) { "
    f"{_RATE_LIMIT} "
    + _OWNED_BOARD.format(
        selection=_ITEMS.format(first="$first", after="after: $after, ")
        + f" {{ totalCount pageInfo {{ hasNextPage endCursor }} nodes {{ {_ITEM_SELECTION} }} }}"
    )
    + " }"
)
"""One page of the board's items that `$filter` selects, archived ones left out."""

BOARD_CARD_QUERY = (
    f"query {BOARD_CARD_OPERATION}($id: ID!, $fieldValues: Int!) {{ {_RATE_LIMIT} "
    f"node(id: $id) {{ ... on ProjectV2Item {{ isArchived {_ITEM_SELECTION} }} }} }}"
)
"""One board item by its node id, archived or not, with the fields a page holds."""

BOARD_BUDGET_QUERY = (
    f"query {BOARD_BUDGET_OPERATION}($owner: String!, $number: Int!, $filter: String!) {{ "
    f"{_RATE_LIMIT} "
    + _OWNED_BOARD.format(selection=_ITEMS.format(first="1", after="") + " { totalCount }")
    + " }"
)
"""The points left, and how many items the read of `$filter` will page through."""

GRAPHQL_BUDGET_QUERY = f"query {GRAPHQL_BUDGET_OPERATION} {{ {_RATE_LIMIT} }}"
"""The points left, read from GraphQL itself; `gh api rate_limit` (REST) has reported 4,899
GraphQL points left while GraphQL's own `rateLimit` reported 17."""


def _graphql_args(query: str, *fields: tuple[str, str], typed: tuple[str, ...] = ()) -> list[str]:
    raw = [part for name, value in fields for part in ("-f", f"{name}={value}")]
    return ["api", "graphql", "-f", f"query={query}", *raw, *typed]


def board_items_args(
    owner: str,
    number: int | str,
    board_filter: str,
    *,
    after: str | None = None,
    first: int = DEFAULT_GH_PROJECT_ITEM_PAGE_SIZE,
) -> list[str]:
    """The `gh` arguments of one page of board `number`'s items that `board_filter` selects; the
    first page passes no cursor."""
    cursor = (("after", after),) if after is not None else ()
    return _graphql_args(
        BOARD_ITEMS_QUERY,
        ("owner", owner),
        ("filter", board_filter),
        *cursor,
        typed=(
            "-F",
            f"number={number}",
            "-F",
            f"first={first}",
            "-F",
            f"fieldValues={DEFAULT_GH_PROJECT_FIELD_LIMIT}",
        ),
    )


def board_budget_args(owner: str, number: int | str, board_filter: str) -> list[str]:
    """The `gh` arguments of the query a board read asks first: the points left and its total."""
    return _graphql_args(
        BOARD_BUDGET_QUERY,
        ("owner", owner),
        ("filter", board_filter),
        typed=("-F", f"number={number}"),
    )


def board_card_args(card_id: str) -> list[str]:
    """The `gh` arguments of the read of one board item by its node id."""
    return _graphql_args(
        BOARD_CARD_QUERY,
        ("id", card_id),
        typed=("-F", f"fieldValues={DEFAULT_GH_PROJECT_FIELD_LIMIT}"),
    )


def graphql_budget_args() -> list[str]:
    """The `gh` arguments of the query that reads the GraphQL points left."""
    return _graphql_args(GRAPHQL_BUDGET_QUERY)


class GraphQLBudget(BaseModel):
    """GraphQL's rate limit as a response reports it: what the query cost, and what is left."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    cost: int
    limit: int
    remaining: int
    used: int
    reset_at: datetime = Field(alias="resetAt")


class GraphQLSpend(BaseModel):
    """The GraphQL points a run spent and the points left, as GraphQL reported them."""

    model_config = ConfigDict(frozen=True)

    spent: int
    remaining: int
    reset_at: datetime
    reset_during_run: bool = False

    def line(self) -> str:
        """The one line a run ends with."""
        texts = MESSAGES.roadmap
        template = texts.graphql_spend_since_reset if self.reset_during_run else texts.graphql_spend
        return template.format(
            spent=self.spent, remaining=self.remaining, reset=utc_clock(self.reset_at)
        )

    def round_line(self, repo: str) -> str:
        """The one line a Service round of `repo` ends with: the points are the account's, which
        every repository's rounds and other tools share (#1400)."""
        texts = MESSAGES.roadmap
        template = (
            texts.graphql_round_spend_since_reset
            if self.reset_during_run
            else texts.graphql_round_spend
        )
        return template.format(
            repo=repo, spent=self.spent, remaining=self.remaining, reset=utc_clock(self.reset_at)
        )


def spend_between(first: GraphQLBudget, last: GraphQLBudget) -> GraphQLSpend:
    """What a run spent from the first response that reported the budget to the last: the
    points used between them and the first query's own cost. A run the hourly reset crossed
    counts what it spent since the reset."""
    reset = last.reset_at != first.reset_at
    spent = last.used if reset else last.used - first.used + first.cost
    return GraphQLSpend(
        spent=spent, remaining=last.remaining, reset_at=last.reset_at, reset_during_run=reset
    )


class _PageInfo(BaseModel):
    has_next_page: bool = Field(alias="hasNextPage")
    end_cursor: str | None = Field(default=None, alias="endCursor")


class _ItemConnection(BaseModel):
    total_count: int = Field(alias="totalCount")
    page_info: _PageInfo | None = Field(default=None, alias="pageInfo")
    nodes: list[dict[str, Any]] = Field(default_factory=list)


_ITEMS_PATH = AliasPath("data", "repositoryOwner", "projectV2", "items")


class BoardBudgetPayload(BaseModel):
    """The answer to `RoadmapBoardBudget`."""

    rate_limit: GraphQLBudget = Field(validation_alias=AliasPath("data", "rateLimit"))
    items: _ItemConnection = Field(validation_alias=_ITEMS_PATH)


class BoardItemsPage(BaseModel):
    """The answer to one `RoadmapBoardItems` page."""

    rate_limit: GraphQLBudget = Field(validation_alias=AliasPath("data", "rateLimit"))
    items: _ItemConnection = Field(validation_alias=_ITEMS_PATH)

    def listed(self) -> list[dict[str, Any]]:
        """The page's items shaped as `gh project item-list` lists them."""
        return [listing_item(node) for node in self.items.nodes]

    def next_cursor(self) -> str | None:
        """The cursor of the next page, or None after the last."""
        info = self.items.page_info
        return info.end_cursor if info is not None and info.has_next_page else None


class GraphQLBudgetPayload(BaseModel):
    """The answer to `RoadmapGraphQLBudget`."""

    rate_limit: GraphQLBudget = Field(validation_alias=AliasPath("data", "rateLimit"))


class _GraphQLError(BaseModel):
    type: str | None = None


class BoardCardPayload(BaseModel):
    """The answer to `RoadmapBoardCard`. A node id that resolves to nothing comes back as a null
    node with a `NOT_FOUND` error, which `gh` reports by exiting 1 with the answer on stdout."""

    rate_limit: GraphQLBudget = Field(validation_alias=AliasPath("data", "rateLimit"))
    node: dict[str, Any] | None = Field(default=None, validation_alias=AliasPath("data", "node"))
    errors: list[_GraphQLError] = Field(default_factory=list)

    def is_gone(self) -> bool:
        """Whether GitHub says the node does not exist, and says nothing else went wrong."""
        return (
            self.node is None
            and bool(self.errors)
            and all(error.type == "NOT_FOUND" for error in self.errors)
        )

    def is_archived(self) -> bool:
        """Whether the item is on the board but archived."""
        return bool((self.node or {}).get("isArchived"))

    def listed(self, *, archived: bool = False) -> dict[str, Any] | None:
        """The item shaped as `gh project item-list` lists it, or None when it is gone or not a
        board item, or archived unless `archived`."""
        node = self.node or {}
        if "id" not in node or (self.is_archived() and not archived):
            return None
        return listing_item(node)


def listing_item(node: dict[str, Any]) -> dict[str, Any]:
    """A board item node in the shape `gh project item-list` gives it: content keyed `type`,
    `repository` as `owner/name`, and each field's value under its name, first letter
    lower-cased."""
    content = dict(node.get("content") or {})
    if "__typename" in content:
        content["type"] = content.pop("__typename")
    repository = content.get("repository")
    if isinstance(repository, dict):
        content["repository"] = repository.get("nameWithOwner")
    values = {
        item_list_key(value["field"]["name"]): next(
            value[key] for key in ("name", "text", "date") if key in value
        )
        for value in (node.get("fieldValues") or {}).get("nodes", [])
        if value and (value.get("field") or {}).get("name")
    }
    return {"id": node["id"], "content": content, **values}


def item_list_key(field_name: str) -> str:
    """The key `gh project item-list` gives a field's value: the name, first letter lower-cased."""
    return field_name[:1].lower() + field_name[1:]


def read_cost(total: int, page_points: int) -> int:
    """The points a read of `total` items is taken to cost: its pages, at least one."""
    return max(1, math.ceil(total / DEFAULT_GH_PROJECT_ITEM_PAGE_SIZE)) * page_points


def _refusal(
    template: str, budget: GraphQLBudget, operation: str, what: str, **details: int
) -> GitHubRateLimitError:
    """The error refusing a request on `what` while the budget is too low: the message names the
    points left and the reset, and the details carry both, the reset under
    `CONST_GRAPHQL_REFUSAL_RESET_KEY` (#1400)."""
    return GitHubRateLimitError(
        template.format(
            remaining=budget.remaining,
            reset=utc_clock(budget.reset_at),
            floor=DEFAULT_GH_GRAPHQL_BUDGET_FLOOR,
            what=what,
            **details,
        ),
        subcommand="graphql",
        operation=operation,
        details={
            "remaining": budget.remaining,
            **details,
            CONST_GRAPHQL_REFUSAL_RESET_KEY: budget.reset_at.isoformat(),
        },
    )


def require_budget(budget: GraphQLBudget, cost: int, what: str) -> None:
    """Refuse a read, before it spends anything, when it would leave less than the floor."""
    if budget.remaining - cost < DEFAULT_GH_GRAPHQL_BUDGET_FLOOR:
        template = MESSAGES.roadmap.graphql_budget_refused
        raise _refusal(template, budget, "roadmap.read", what, cost=cost)


def require_write_floor(budget: GraphQLBudget, what: str) -> None:
    """Refuse a write, before it starts, while fewer points than the floor are left."""
    if budget.remaining < DEFAULT_GH_GRAPHQL_BUDGET_FLOOR:
        template = MESSAGES.roadmap.graphql_budget_write_floor
        raise _refusal(template, budget, "roadmap.write", what)


def require_floor(budget: GraphQLBudget, what: str, page: int) -> None:
    """Stop a read before page `page` while fewer points than the floor are left."""
    if budget.remaining < DEFAULT_GH_GRAPHQL_BUDGET_FLOOR:
        template = MESSAGES.roadmap.graphql_budget_floor
        raise _refusal(template, budget, "roadmap.read", what, page=page)


def refusal_reset(exc: BaseException) -> datetime | None:
    """The reset a GraphQL budget refusal names, or None for any other error, a rate limiter
    error included."""
    if not isinstance(exc, GitHubRateLimitError):
        return None
    reset = exc.details.get(CONST_GRAPHQL_REFUSAL_RESET_KEY)
    return None if reset is None else datetime.fromisoformat(reset)


def utc_clock(moment: datetime) -> str:
    """A reset time as the budget messages name it: hours and minutes, in UTC."""
    return moment.strftime("%H:%M UTC")


__all__ = [
    "BOARD_BUDGET_OPERATION",
    "BOARD_BUDGET_QUERY",
    "BOARD_CARD_OPERATION",
    "BOARD_CARD_QUERY",
    "BOARD_ITEMS_OPERATION",
    "BOARD_ITEMS_QUERY",
    "GRAPHQL_BUDGET_OPERATION",
    "GRAPHQL_BUDGET_QUERY",
    "BoardBudgetPayload",
    "BoardCardPayload",
    "BoardItemsPage",
    "GraphQLBudget",
    "GraphQLBudgetPayload",
    "GraphQLSpend",
    "board_budget_args",
    "board_card_args",
    "board_items_args",
    "graphql_budget_args",
    "item_list_key",
    "listing_item",
    "read_cost",
    "refusal_reset",
    "require_budget",
    "require_floor",
    "require_write_floor",
    "spend_between",
    "utc_clock",
]
