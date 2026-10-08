"""A fake GitHub answering the `gh` commands `devops gh project reconcile` and `sync` send (#892).

`ProjectGitHub` holds a board, as `gh project item-list` lists it, and a repository's issues and
pull requests, as REST lists them. It answers the board's budget query and pages through
`BoardServer`, the board's Status and Priority options through `gh project field-list`, the
issues and pull requests a listing's `state` selects, every page of them, and records each
`item-edit` and `item-add`. For sync it also answers the scope check's and the owner's
`gh project list`, the repository's linked boards, `gh project link` and the signed-in login.
Any other command fails the test. It starts no `gh` and opens no socket.
"""

from __future__ import annotations

import itertools
import json
import subprocess
from collections.abc import Callable, Iterable, Sequence
from typing import Any
from urllib.parse import parse_qs, urlsplit

from tests.roadmap_board_fake import BoardServer

REPO = "o/r"
BOARD_TITLE = "Roadmap"
STATUSES = ("New", "Ready", "In Progress", "In Review", "Done", "Blocked")
PRIORITIES = ("P0-Critical", "P1-High", "P2-Medium", "P3-Low")


def issue_url(number: int, kind: str = "issues") -> str:
    return f"https://example.com/{REPO}/{kind}/{number}"


def card(number: int, kind: str = "issues", **fields: str) -> dict[str, Any]:
    """A card on the board, listed as `gh project item-list` lists it."""
    content_type = "PullRequest" if kind == "pull" else "Issue"
    content = {"type": content_type, "number": number, "url": issue_url(number, kind)}
    return {"id": f"PVTI_{number}", "content": {**content, "repository": REPO}, **fields}


def issue(number: int, state: str = "open", labels: tuple[str, ...] = ()) -> dict[str, Any]:
    """An issue as the REST issues listing gives it."""
    return {
        "number": number,
        "html_url": issue_url(number),
        "state": state,
        "labels": [{"name": name} for name in labels],
    }


def pull(
    number: int, state: str = "open", *, merged: bool = False, body: str = ""
) -> dict[str, Any]:
    """A pull request as the REST pulls listing gives it."""
    return {
        "number": number,
        "html_url": issue_url(number, "pull"),
        "state": state,
        "draft": False,
        "merged_at": "2026-10-01T00:00:00Z" if merged else None,
        "title": f"fix: change {number}",
        "body": body,
        "labels": [],
    }


class ProjectGitHub:
    """Answers reconcile's and sync's `gh` commands; `fail_edits` names the 1-based edits that
    exit 1 with `write_error` on stderr, and `on_edit` runs after each edit with its count."""

    def __init__(
        self,
        cards: list[dict[str, Any]],
        issues: Sequence[dict[str, Any]] = (),
        pulls: Sequence[dict[str, Any]] = (),
        *,
        remaining: int = 5000,
        statuses: tuple[str, ...] = STATUSES,
        fail_edits: tuple[int, ...] = (),
        write_error: str = "GraphQL: the write failed",
        on_edit: Callable[[int], None] | None = None,
    ) -> None:
        self.server = BoardServer({"items": cards, "totalCount": len(cards)}, remaining=remaining)
        self.issues = list(issues)
        self.pulls = list(pulls)
        self.statuses = statuses
        self.fail_edits = fail_edits
        self.write_error = write_error
        self.on_edit = on_edit
        self.sent: list[list[str]] = []
        self.edits: list[tuple[str, str, str]] = []
        self.adds: list[list[str]] = []
        self.links: list[list[str]] = []

    def run_gh(self, cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        """`run_gh`'s stand-in: `cmd` starts with `gh`."""
        return self(cmd)

    def __call__(self, cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        args = list(cmd[1:])
        self.sent.append(args)
        code, stdout = self._answer(args)
        return subprocess.CompletedProcess(cmd, code, stdout, "" if code == 0 else self.write_error)

    def _answer(self, args: list[str]) -> tuple[int, str]:
        if args[:2] == ["api", "graphql"]:
            if any("repository(owner: $owner" in arg for arg in args):
                return 0, json.dumps(self._linked_boards())
            return 0, json.dumps(self.server(args))
        if args[:2] == ["project", "field-list"]:
            return 0, json.dumps(self._fields())
        if args[:2] == ["project", "item-edit"]:
            return self._edit(args)
        if args[:2] == ["project", "item-add"]:
            self.adds.append(args)
            return 0, "{}"
        if args[:2] == ["project", "list"]:
            return 0, json.dumps({"projects": [], "totalCount": 0})
        if args[:2] == ["project", "link"]:
            self.links.append(args)
            return 0, ""
        if args[:2] == ["api", "user"]:
            return 0, "someone\n"
        if args[0] == "api":
            return 0, json.dumps(self._listing(next(a for a in args if a.startswith("repos/"))))
        raise AssertionError(f"unexpected gh call: {args}")

    def _fields(self) -> dict[str, Any]:
        """`gh project field-list`'s reply: the board's Status and Priority fields."""
        fields = [
            {
                "id": f"PVTSSF_{name}",
                "name": name,
                "options": [{"id": f"OPT_{n}", "name": option} for n, option in enumerate(names)],
            }
            for name, names in (("Status", self.statuses), ("Priority", PRIORITIES))
        ]
        return {"fields": fields, "totalCount": len(fields)}

    def _linked_boards(self) -> dict[str, Any]:
        """The repository's linked boards, as GraphQL gives them: board 2, `BOARD_TITLE`."""
        board = {"number": 2, "title": BOARD_TITLE, "id": "PVT_2", "url": "https://example.com/2"}
        return {"data": {"repository": {"projectsV2": {"nodes": [board]}}}}

    def _edit(self, args: list[str]) -> tuple[int, str]:
        def flag(name: str) -> str:
            return args[args.index(name) + 1]

        self.edits.append((flag("--url"), flag("--field"), flag("--value")))
        count = len(self.edits)
        if self.on_edit is not None:
            self.on_edit(count)
        return (1, "") if count in self.fail_edits else (0, "{}")

    def _listing(self, endpoint: str) -> list[dict[str, Any]]:
        parts = urlsplit(endpoint)
        query = parse_qs(parts.query)
        if int(query.get("page", ["1"])[0]) > 1:
            return []
        state = query["state"][0]
        items = self.pulls if parts.path.endswith("/pulls") else self.issues
        return [item for item in items if state == "all" or item["state"] == state]

    def kinds(self) -> list[str]:
        """The requests sent, one entry per run of the same kind."""
        return collapse(request_kind(args) for args in self.sent)


def request_kind(args: list[str]) -> str:
    """A request's kind: a board query's operation, a listing's path, or the gh command."""
    joined = " ".join(args)
    operations = ("RoadmapBoardBudget", "RoadmapBoardItems")
    listing = next((a for a in args if a.startswith("repos/")), None)
    if args[:2] == ["api", "graphql"]:
        return next((op for op in operations if op in joined), "api graphql")
    if args[0] == "api" and listing is not None:
        return urlsplit(listing).path
    return " ".join(args[:2])


def collapse(kinds: Iterable[str]) -> list[str]:
    """`kinds` with each run of one kind kept once."""
    return [kind for kind, _ in itertools.groupby(kinds)]
