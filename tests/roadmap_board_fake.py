"""A fake GitHub answering the roadmap store's `gh` commands (#1125, #1361).

`BoardServer` holds a board listed as `gh project item-list` lists it (the recorded fixtures keep
that shape) and answers `RoadmapBoardBudget` and `RoadmapBoardItems` as GraphQL would: archived
items left out, `is:open` honoured from each item's `content.state`, a page at a time by cursor,
each answer carrying `rateLimit` with the points it cost and the points left. It answers
`RoadmapBoardCard` by node id, archived items included, and a node id it doesn't hold as GitHub
does: a null node with a `NOT_FOUND` error, `gh` exiting 1. A card in `lagging` is left out of
that many listings, as GitHub's listing showed a new card up to two minutes after its add.

`GitHubFake` is a whole repository and its board at the `gh` process edge: REST issues,
milestones, labels, comments, events and files, the board's fields, and the `gh project`
writes, each applied to what later reads return. It also answers the project metrics reads
(the repository, its Actions runs and its traffic), `gh api user` with its `login`, and
`gh api rate_limit` with a full quota that resets in a minute. It keeps every argv, and charges
each GraphQL request the points GitHub's own estimate (`rateLimit(dryRun: true)`, board #2,
2026-10-08) gives its shape (`GRAPHQL_POINTS`). Closing an issue runs the board's built-in
"Item closed" workflow, which sets its card's Status to Done. `item-add` names the card an issue
already has, archived or not, and `item-archive --undo` restores an archived one with its fields
(#1403). Neither starts `gh` or opens a socket. `GitHubFake.process` stands in for
`subprocess.run` itself, answering `gh` and passing every other program, such as `git`, to the
real one.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable, Iterable
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.roadmap.board_read import (
    BOARD_BUDGET_OPERATION,
    BOARD_CARD_OPERATION,
    BOARD_ITEMS_OPERATION,
    item_list_key,
)

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
    """An item-list entry as a `ProjectV2Item` node, `isArchived` included."""
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
    return {
        "id": entry["id"],
        "isArchived": bool(entry.get("isArchived")),
        "content": content,
        "fieldValues": {"nodes": values},
    }


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
        card_cost: int = 1,
        on_page: Callable[[BoardServer, int], None] | None = None,
    ) -> None:
        self._source = listing
        # Kept, not copied, so a test's write to the listing shows in the next read.
        self.listing: Listing = listing if isinstance(listing, dict) else {}
        self.remaining = remaining
        self.page_cost = page_cost
        self.probe_cost = probe_cost
        self.card_cost = card_cost
        self.on_page = on_page
        self.pages = 0
        self.spent = 0
        # Card ids the next listings leave out, with how many listings each is left out of.
        self.lagging: dict[str, int] = {}

    def selected(self, board_filter: str) -> list[dict[str, Any]]:
        """The items a read of `board_filter` sees: not archived, not lagging, and open for
        `is:open`."""
        return [
            entry
            for entry in self.listing["items"]
            if not entry.get("isArchived")
            and not self.lagging.get(entry["id"])
            and ("is:open" not in board_filter or entry["content"].get("state", "OPEN") == "OPEN")
        ]

    def entry(self, card_id: str) -> dict[str, Any] | None:
        """The listing's entry for `card_id`, archived or not."""
        return next((entry for entry in self.listing["items"] if entry["id"] == card_id), None)

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

    def __call__(self, args: list[str]) -> Any:
        variables = gh_variables(args)
        if BOARD_CARD_OPERATION in variables["query"]:
            return self._card(variables["id"])
        board_filter = variables["filter"]
        if BOARD_BUDGET_OPERATION in variables["query"]:
            if callable(self._source):
                self.listing = deepcopy(self._source())
            self.lagging = {card: left - 1 for card, left in self.lagging.items() if left > 1}
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

    def _card(self, card_id: str) -> Any:
        """One card by node id; one this board doesn't hold answers as GitHub does, exit 1."""
        if callable(self._source) and not self.listing:
            self.listing = deepcopy(self._source())
        found = self.entry(card_id)
        node = graphql_node(found) if found is not None else None
        answer: dict[str, Any] = {"data": {"rateLimit": self._rate_limit(self.card_cost)}}
        answer["data"]["node"] = node
        if found is not None:
            return answer
        message = f"Could not resolve to a node with the global id of '{card_id}'"
        answer["errors"] = [{"type": "NOT_FOUND", "path": ["node"], "message": message}]
        return (1, json.dumps(answer))


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
    items = {"items": entries, "totalCount": len(entries)}
    board_filter_args = ["-f", "query=query RoadmapBoardItems", "-f", "filter=", "-F", "first=100"]
    return json.dumps(BoardServer(items)(board_filter_args))


# ── A whole repository and its board ──────────────────────────────────────────

GRAPHQL_POINTS: dict[str, int] = {
    "mutation": 1,
    "query": 1,
    "name_resolution": 101,
}
"""What GitHub's own estimate gives each GraphQL request shape on board #2 (2026-10-08, #1361):
a query that pages no board items, such as the fields, a one-card read or a page of the store's
board query, and a mutation cost about 1 point. `gh project field-list`, and `gh project
item-edit` given `--url` or `--field`, first fetch the board's first 100 items with all their
field values (`ProjectFields`, `firstItems` 100): about 101 more. `gh project item-add`,
`item-create` and `item-archive` are charged as one mutation, though gh first resolves the
board's owner and the board, and for an add the issue, with small queries of its own that this
fake leaves out, so its totals for a placement are a floor of a few points under GitHub's."""

BOARD_ID = "PVT_board"
OPTIONS: dict[str, tuple[str, ...]] = {
    "Status": ("New", "Ready", "In Progress", "In Review", "Done", "Blocked"),
    "Priority": ("P0-Critical", "P1-High", "P2-Medium", "P3-Low"),
    "Value": ("High", "Medium", "Low"),
    "Effort": ("Low", "Medium", "High"),
}
JOB_RECORD = "Job record"


def field_id(name: str) -> str:
    """The node id `GitHubFake` gives the board field `name`."""
    return f"PVTF_{name.replace(' ', '_').lower()}"


def option_id(field: str, name: str) -> str:
    """The node id `GitHubFake` gives option `name` of field `field`."""
    return f"{field_id(field)}/{name.replace(' ', '_')}"


def fields_reply(board_id: str = BOARD_ID) -> dict[str, Any]:
    """The answer to the store's fields query: Status, Priority, Value, Effort and the job
    record, with the board's node id."""
    nodes: list[dict[str, Any]] = [
        {
            "id": field_id(name),
            "name": name,
            "dataType": "SINGLE_SELECT",
            "options": [{"id": option_id(name, option), "name": option} for option in options],
        }
        for name, options in OPTIONS.items()
    ]
    nodes.append({"id": field_id(JOB_RECORD), "name": JOB_RECORD, "dataType": "TEXT"})
    connection = {"totalCount": len(nodes), "nodes": nodes}
    return {"data": {"repositoryOwner": {"projectV2": {"id": board_id, "fields": connection}}}}


def _flags(args: list[str]) -> dict[str, str]:
    """A `gh` argv's `--name value` flags, and each bare `--flag` as an empty value."""
    flags: dict[str, str] = {}
    for index, arg in enumerate(args):
        if arg.startswith("--"):
            following = args[index + 1] if index + 1 < len(args) else "--"
            flags[arg] = "" if following.startswith("--") else following
    return flags


class GitHubFake:
    """One repository's issues, milestones and board, answering the store's `gh` commands.

    `issues` maps a number to its REST payload; `on_board` numbers start as cards with the
    given `cards` fields. `lag` is how many board listings leave a card just added out. `files`
    maps a path to its text, or to the `(exit code, output)` `gh` gives for it, such as a 502.
    """

    def __init__(
        self,
        repo: str,
        *,
        milestones: Iterable[dict[str, Any]] = (),
        files: dict[str, str | tuple[int, str]] | None = None,
        events: Iterable[dict[str, Any]] = (),
        lag: int = 0,
        commits: Iterable[str] = (),
        login: str = "roadmap-bot",
    ) -> None:
        self.repo = repo
        self.login = login
        self.milestones = list(milestones)
        self.files = dict(files or {})
        self.events = list(events)
        self.commits = set(commits)
        self.lag = lag
        self.issues: dict[int, dict[str, Any]] = {}
        self.comments: dict[int, list[str]] = {}
        self.board = BoardServer({"items": [], "totalCount": 0})
        self.calls: list[list[str]] = []
        self.points = 0

    # ── Seeding ──

    def seed_issue(
        self,
        number: int,
        title: str = "",
        *,
        state: str = "open",
        labels: Iterable[str] = (),
        milestone: str | None = None,
        card: dict[str, str] | None = None,
    ) -> None:
        """Issue `number`, and its card holding `card`'s fields when it is on the board."""
        self.issues[number] = {
            "number": number,
            "title": title or f"Issue {number}",
            "html_url": f"https://github.com/{self.repo}/issues/{number}",
            "body": "",
            "state": state,
            "labels": [{"name": label} for label in labels],
            "milestone": self._milestone(milestone),
            "node_id": f"I_{number}",
            "author_association": "COLLABORATOR",
            "created_at": "2026-10-01T00:00:00Z",
        }
        if card is not None:
            self._put_card(number, card)

    def card_id(self, number: int) -> str:
        return f"PVTI_{number}"

    def card(self, number: int) -> dict[str, Any] | None:
        """Issue `number`'s board entry, as the listing holds it."""
        return self.board.entry(self.card_id(number))

    def graphql_calls(self, *names: str) -> list[list[str]]:
        """The GraphQL requests sent, only those naming one of `names` when given."""
        graphql = [args for args in self.calls if args[:2] == ["api", "graphql"]]
        graphql += [args for args in self.calls if args[0] == "project"]
        return [args for args in graphql if not names or any(n in " ".join(args) for n in names)]

    # ── The process edge ──

    def __call__(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        reply = self._answer(args, kwargs.get("input"))
        returncode, output = reply if isinstance(reply, tuple) else (0, reply)
        text = output if isinstance(output, str) else json.dumps(output)
        return subprocess.CompletedProcess(args, returncode, text, "" if returncode == 0 else text)

    def process(
        self, run: Callable[..., subprocess.CompletedProcess[str]]
    ) -> Callable[..., subprocess.CompletedProcess[str]]:
        """A stand-in for `subprocess.run` that answers `gh`, given as a list or a tuple, as this
        fake, raising `CalledProcessError` for a failed answer under `check=True` as `run` does,
        and hands every other program to `run`, the real `subprocess.run`."""

        def dispatch(cmd: Any, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if not (isinstance(cmd, list | tuple) and cmd and Path(cmd[0]).name == CONST_GH_CLI):
                return run(cmd, *args, **kwargs)
            answer = self(list(cmd[1:]), **kwargs)
            if kwargs.get("check"):
                answer.check_returncode()
            return answer

        return dispatch

    def _answer(self, args: list[str], stdin: str | None) -> Any:
        if args[0] == "project":
            return self._project(args)
        if args[:2] == ["api", "graphql"]:
            return self._graphql(args, stdin)
        if args[:2] == ["api", "user"]:
            return f"{self.login}\n"
        if args[:2] == ["api", "rate_limit"]:
            reset = int(time.time()) + 60
            quota = {"limit": 5000, "remaining": 5000, "used": 0, "reset": reset}
            return {"resources": {name: quota for name in ("core", "graphql", "search")}}
        assert args[0] == "api", f"not a gh command the store sends: {args}"
        return self._rest(args)

    def _graphql(self, args: list[str], stdin: str | None) -> Any:
        query = stdin or gh_variables(args).get("query", "")
        if "RoadmapBoard" in query:
            before = self.board.spent
            reply = self.board(args)
            self.points += self.board.spent - before
            return reply
        self.points += GRAPHQL_POINTS["query"]
        answers: list[tuple[str, Callable[[], Any]]] = [
            ("RoadmapGraphQLBudget", lambda: budget_reply(self.board.remaining)),
            ("fields(first", fields_reply),
            ("timelineItems", self._timeline),
            ("defaultBranchRef", self._default_branch),
            ("milestone(number", self._release_pull_requests),
            ("closeIssue", lambda: self._close_as_duplicate(stdin or "")),
        ]
        found = next((answer for key, answer in answers if key in query), None)
        assert found is not None, f"no fake for the GraphQL request: {query[:120]}"
        return found()

    def _timeline(self) -> dict[str, Any]:
        connection = {"totalCount": 0, "nodes": []}
        return {"data": {"repository": {"issue": {"timelineItems": connection}}}}

    def _default_branch(self) -> dict[str, Any]:
        branch = {"name": "main", "target": {"oid": "a" * 40}}
        return {"data": {"repository": {"defaultBranchRef": branch}}}

    def _release_pull_requests(self) -> dict[str, Any]:
        connection = {"totalCount": 0, "nodes": []}
        return {"data": {"repository": {"milestone": {"pullRequests": connection}}}}

    # ── gh project ──

    def _project(self, args: list[str]) -> Any:
        flags, command = _flags(args), args[1]
        named = command == "field-list" or (
            command == "item-edit" and ("--url" in flags or "--field" in flags)
        )
        self.points += GRAPHQL_POINTS["mutation"] + named * GRAPHQL_POINTS["name_resolution"]
        assert not named, f"a board command gh resolves by reading 100 items first: {args}"
        if command == "item-add":
            number = int(flags["--url"].rsplit("/", 1)[1])
            card = self.card(number) or self._put_card(number, {}, lag=self.lag)
            return {"id": card["id"], "title": card["content"]["title"], "type": "Issue"}
        if command == "item-edit":
            return self._edit(flags)
        if command == "item-archive":
            return self._unarchive(flags)
        if command == "item-create":
            card = {
                "id": "PVTI_draft",
                "content": {"type": "DraftIssue", "title": flags["--title"]},
            }
            self.board.listing["items"].append(card)
            return {"id": card["id"], "title": flags["--title"], "type": "DraftIssue"}
        raise AssertionError(f"no fake for: {args}")

    def _edit(self, flags: dict[str, str]) -> str:
        assert flags["--project-id"] == BOARD_ID, flags
        entry = self.board.entry(flags["--id"])
        assert entry is not None, f"no card {flags['--id']}"
        names = {field_id(name): name for name in (*OPTIONS, JOB_RECORD)}
        key = item_list_key(names[flags["--field-id"]])
        if "--clear" in flags:
            entry.pop(key, None)
        elif "--text" in flags:
            entry[key] = flags["--text"]
        else:
            entry[key] = flags["--single-select-option-id"].split("/", 1)[1].replace("_", " ")
        return ""

    def _unarchive(self, flags: dict[str, str]) -> dict[str, Any]:
        """`item-archive --undo`: the card leaves the archive with its fields, printed as gh
        prints it; the store never archives a card."""
        assert "--undo" in flags, f"the store archived a card: {flags}"
        entry = self.board.entry(flags["--id"])
        assert entry is not None, f"no card {flags['--id']}"
        entry.pop("isArchived", None)
        content = entry["content"]
        return {"id": entry["id"], "title": content["title"], "type": content["type"]}

    def _put_card(self, number: int, fields: dict[str, str], *, lag: int = 0) -> dict[str, Any]:
        issue = self.issues[number]
        content = {
            "type": "Issue",
            "number": number,
            "repository": self.repo,
            "title": issue["title"],
            "url": issue["html_url"],
            "state": issue["state"].upper(),
        }
        card: dict[str, Any] = {"id": self.card_id(number), "content": content, **fields}
        self.board.listing["items"].append(card)
        self.board.listing["totalCount"] = len(self.board.listing["items"])
        if lag:
            self.board.lagging[card["id"]] = lag
        return card

    # ── REST ──

    def _rest(self, args: list[str]) -> Any:
        method = args[args.index("-X") + 1] if "-X" in args else "GET"
        path = next(arg for arg in args[1:] if "/" in arg and not arg.startswith(("-", "Accept")))
        fields = dict(
            args[index + 1].split("=", 1)
            for index, arg in enumerate(args)
            if arg in ("-f", "-F") and "=" in args[index + 1]
        )
        url = urlsplit(path)
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        if url.path == f"repos/{self.repo}":
            open_issues = sum(issue["state"] == "open" for issue in self.issues.values())
            return {"stargazers_count": 0, "forks_count": 0, "open_issues_count": open_issues}
        parts = url.path.removeprefix(f"repos/{self.repo}/").split("/")
        return self._rest_route(method, url.path, parts, query, fields, args)

    def _rest_route(
        self,
        method: str,
        path: str,
        parts: list[str],
        query: dict[str, str],
        fields: dict[str, str],
        args: list[str],
    ) -> Any:
        page = int(query.get("page", "1"))
        if path == "search/issues":
            return {"total_count": 0, "incomplete_results": False}
        if parts[0] == "contents":
            name = unquote("/".join(parts[1:]))
            return self.files[name] if name in self.files else (1, "gh: Not Found (HTTP 404)")
        if parts[0] == "commits":
            return {"sha": parts[1]} if parts[1] in self.commits else (1, "HTTP 422")
        if parts[0] == "releases":
            return (1, "gh: Not Found (HTTP 404)")
        if parts == ["actions", "runs"]:
            return {"total_count": 0, "workflow_runs": []}
        if parts[0] == "traffic":
            return [] if parts[1] == "popular" else {"count": 0, "uniques": 0}
        if parts[0] == "milestones":
            return self.milestones if page == 1 else []
        if parts == ["issues", "events"]:
            return self.events[(page - 1) * 100 : page * 100]
        if parts == ["issues"]:
            labels = [arg.split("=", 1)[1] for arg in args if arg.startswith("labels[]=")]
            return self._issues(method, query, fields | {"labels": json.dumps(labels)}, page)
        return self._issue_route(method, int(parts[1]), parts[2:], fields, page)

    def _issues(self, method: str, query: dict[str, str], fields: dict[str, str], page: int) -> Any:
        if method == "POST":
            number = max(self.issues, default=0) + 1
            self.seed_issue(number, fields["title"], labels=json.loads(fields["labels"]))
            self.issues[number]["body"] = fields.get("body", "")
            return self.issues[number]
        listed = [
            issue
            for issue in self.issues.values()
            if query.get("state", "open") in ("all", issue["state"])
            and self._in_milestone(issue, query.get("milestone"))
        ]
        return listed[(page - 1) * 100 : page * 100]

    def _issue_route(
        self, method: str, number: int, rest: list[str], fields: dict[str, str], page: int
    ) -> Any:
        issue = self.issues[number]
        if rest == ["labels"]:
            issue["labels"].append({"name": fields["labels[]"]})
            return issue["labels"]
        if rest == ["comments"] and method == "POST":
            self.comments.setdefault(number, []).append(fields["body"])
            return {}
        if rest == ["comments"]:
            bodies = self.comments.get(number, []) if page == 1 else []
            return [{"body": body} for body in bodies]
        if method == "PATCH" and "milestone" in fields:
            title = next(
                (m["title"] for m in self.milestones if str(m["number"]) == fields["milestone"]),
                None,
            )
            issue["milestone"] = self._milestone(title)
        if method == "PATCH" and fields.get("state") == "closed":
            self.close(number, fields["state_reason"])
        return issue

    def close(self, number: int, reason: str) -> None:
        """Close issue `number` for `reason`, and let the board's built-in "Item closed"
        workflow set its card's Status to Done, as GitHub does after a close."""
        self.issues[number].update(state="closed", state_reason=reason)
        card = self.card(number)
        if card is not None:
            card["content"]["state"] = "CLOSED"
            card["status"] = "Done"

    def _close_as_duplicate(self, stdin: str) -> dict[str, Any]:
        """The `closeIssue` mutation that closes an issue as a duplicate of another."""
        issue_id = json.loads(stdin)["variables"]["issue"]
        number = next(n for n, issue in self.issues.items() if issue["node_id"] == issue_id)
        self.close(number, "duplicate")
        return {"data": {"closeIssue": {"issue": {"number": number}}}}

    def _milestone(self, title: str | None) -> dict[str, Any] | None:
        found = next((m for m in self.milestones if m["title"] == title), None)
        return {"number": found["number"], "title": title} if found else None

    @staticmethod
    def _in_milestone(issue: dict[str, Any], milestone: str | None) -> bool:
        held = issue["milestone"]
        if milestone is None:
            return True
        if milestone == "none":
            return held is None
        return held is not None and str(held["number"]) == milestone
