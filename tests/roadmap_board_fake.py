"""A fake GitHub answering the roadmap store's GraphQL board reads (#1125).

`BoardServer` holds a board listed as `gh project item-list` lists it (the recorded fixtures keep
that shape) and answers `RoadmapBoardBudget` and `RoadmapBoardItems` as GraphQL would: archived
items left out, `is:open` honoured from each item's `content.state`, a page at a time by cursor,
each answer carrying `rateLimit` with the points it cost and the points left. It starts no `gh`
and opens no socket.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from devops_cli.roadmap.board_read import BOARD_BUDGET_OPERATION, BOARD_ITEMS_OPERATION

BOARD_READ = "RoadmapBoard"
"""The reply key a `RecordedGh` matches both board queries by."""

RESET_AT = "2099-01-01T00:00:00Z"
_NOT_FIELDS = frozenset({"id", "content", "title", "repository", "isArchived"})
_TEXT_FIELDS = frozenset({"job record"})

Listing = dict[str, Any]


def gh_variables(args: list[str]) -> dict[str, str]:
    """The `-f`/`-F` fields of a `gh api graphql` argv, by name."""
    pairs = (args[i + 1] for i, arg in enumerate(args) if arg in ("-f", "-F"))
    return dict(pair.split("=", 1) for pair in pairs)


def graphql_node(entry: dict[str, Any]) -> dict[str, Any]:
    """An item-list entry as a `ProjectV2Item` node."""
    content = deepcopy(entry.get("content") or {})
    content["__typename"] = content.pop("type", "DraftIssue")
    if isinstance(content.get("repository"), str):
        content["repository"] = {"nameWithOwner": content["repository"]}
    values = [
        {
            ("text" if key in _TEXT_FIELDS else "name"): value,
            "field": {"name": key[:1].upper() + key[1:]},
        }
        for key, value in entry.items()
        if key not in _NOT_FIELDS and isinstance(value, str)
    ]
    return {"id": entry["id"], "content": content, "fieldValues": {"nodes": values}}


class BoardServer:
    """Answers the board queries from a listing; `listing` may be a function giving the
    listing at the start of each read."""

    def __init__(
        self,
        listing: Listing | Callable[[], Listing],
        *,
        remaining: int = 5000,
        page_cost: int = 1,
        probe_cost: int = 1,
        on_page: Callable[[BoardServer, int], None] | None = None,
    ) -> None:
        self._source = listing
        # Kept, not copied, so a test's write to the listing shows in the next read.
        self.listing: Listing = listing if isinstance(listing, dict) else {}
        self.remaining = remaining
        self.page_cost = page_cost
        self.probe_cost = probe_cost
        self.on_page = on_page
        self.pages = 0
        self.spent = 0

    def selected(self, board_filter: str) -> list[dict[str, Any]]:
        """The items a read of `board_filter` sees: not archived, and open for `is:open`."""
        return [
            entry
            for entry in self.listing["items"]
            if not entry.get("isArchived")
            and ("is:open" not in board_filter or entry["content"].get("state", "OPEN") == "OPEN")
        ]

    def total(self, board_filter: str) -> int:
        """The filter's total; a listing whose `totalCount` exceeds its items keeps the gap."""
        gap: int = max(0, int(self.listing.get("totalCount", 0)) - len(self.listing["items"]))
        return len(self.selected(board_filter)) + gap

    def _rate_limit(self, cost: int) -> dict[str, Any]:
        self.remaining -= cost
        self.spent += cost
        return {
            "cost": cost,
            "limit": 5000,
            "remaining": self.remaining,
            "used": 5000 - self.remaining,
            "resetAt": RESET_AT,
        }

    def __call__(self, args: list[str]) -> dict[str, Any]:
        variables = gh_variables(args)
        board_filter = variables["filter"]
        if BOARD_BUDGET_OPERATION in variables["query"]:
            if callable(self._source):
                self.listing = deepcopy(self._source())
            items = {"totalCount": self.total(board_filter), "nodes": []}
            return self._answer(self.probe_cost, items)
        assert BOARD_ITEMS_OPERATION in variables["query"]
        start = int(variables.get("after", "0"))
        first = int(variables["first"])
        selected = self.selected(board_filter)
        page = selected[start : start + first]
        end = start + len(page)
        items = {
            "totalCount": self.total(board_filter),
            "pageInfo": {"hasNextPage": end < len(selected), "endCursor": str(end)},
            "nodes": [graphql_node(entry) for entry in page],
        }
        answer = self._answer(self.page_cost, items)
        self.pages += 1
        if self.on_page is not None:
            self.on_page(self, self.pages)
        return answer

    def _answer(self, cost: int, items: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": {
                "rateLimit": self._rate_limit(cost),
                "repositoryOwner": {"projectV2": {"items": items}},
            }
        }


def budget_reply(remaining: int, *, cost: int = 1) -> dict[str, Any]:
    """The answer to `RoadmapGraphQLBudget`."""
    rate_limit = {
        "cost": cost,
        "limit": 5000,
        "remaining": remaining,
        "used": 5000 - remaining,
        "resetAt": RESET_AT,
    }
    return {"data": {"rateLimit": rate_limit}}


def board_page_reply(entries: list[dict[str, Any]]) -> str:
    """The JSON answer to a one-page `RoadmapBoardItems` read holding `entries`, listed as
    `gh project item-list` lists them."""
    import json

    items = {"items": entries, "totalCount": len(entries)}
    board_filter_args = ["-f", "query=query RoadmapBoardItems", "-f", "filter=", "-F", "first=100"]
    return json.dumps(BoardServer(items)(board_filter_args))
