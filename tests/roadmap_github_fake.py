"""A fake GitHub repository answering the roadmap store's `gh` commands (#1125, #1361, #2399).

`GitHubFake` is a whole repository at the `gh` process edge: REST issues, with their labels and
bodies, milestones, comments, events and files, each write applied to what later reads return.
It answers `PATCH` of an issue with its fields as JSON on stdin (`--input -`), as `gh api` sends
them: `labels` replaces the issue's labels and `body` its body. It also answers the project
metrics reads (the repository, its Actions runs and its traffic), `gh api user` with its `login`,
and `gh api rate_limit` with a full quota that resets in a minute. It keeps every argv, and
`project_calls` gives each one that names a project board, so a test shows that a roadmap job
sends none. Neither starts `gh` nor opens a socket. `GitHubFake.process` stands in for
`subprocess.run` itself, answering `gh` and passing every other program, such as `git`, to the
real one.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from devops_cli.config.constants import CONST_GH_CLI
from tests.support.fakes.github import API

PROJECT_WORDS = ("projectV2", "ProjectV2", "roadmap.toml")
"""What a GraphQL request that reads or writes a project board, or a read of the old roadmap
file, names; a `gh project` command is one too."""


def gh_variables(args: list[str]) -> dict[str, str]:
    """The `-f`/`-F` fields of a `gh api graphql` argv, by name."""
    pairs = (args[i + 1] for i, arg in enumerate(args) if arg in ("-f", "-F"))
    return dict(pair.split("=", 1) for pair in pairs)


class GitHubFake:
    """One repository's issues and milestones, answering the store's `gh` commands.

    `issues` maps a number to its REST payload. `files` maps a path to its text, or to the
    `(exit code, output)` `gh` gives for it, such as a 502. `traffic_answer`, when set, is the
    `(exit code, output)` that `gh` gives for every traffic path, such as the 403 that an
    installation token gets (#2752).
    """

    def __init__(
        self,
        repo: str,
        *,
        milestones: Iterable[dict[str, Any]] = (),
        files: dict[str, str | tuple[int, str]] | None = None,
        events: Iterable[dict[str, Any]] = (),
        commits: Iterable[str] = (),
        login: str = "roadmap-bot",
        traffic_answer: tuple[int, str] | None = None,
    ) -> None:
        self.repo = repo
        self.login = login
        self.traffic_answer = traffic_answer
        self.milestones = list(milestones)
        self.files = dict(files or {})
        self.events = list(events)
        self.commits = set(commits)
        self.issues: dict[int, dict[str, Any]] = {}
        self.pulls: dict[int, dict[str, Any]] = {}
        self.label_catalog: list[dict[str, Any]] = []
        self.comments: dict[int, list[str]] = {}
        self.repositories: dict[str, tuple[dict[str, Any], dict[str, Any] | None]] = {}
        self.calls: list[list[str]] = []
        self.stdins: list[str | None] = []

    # ── Seeding ──

    def seed_issue(
        self,
        number: int,
        title: str = "",
        *,
        state: str = "open",
        body: str = "",
        labels: Iterable[str] = (),
        milestone: str | None = None,
        sub_issues: int = 0,
        parent: int | None = None,
        parent_repo: str | None = None,
        pull_request: bool = False,
        author_association: str = "COLLABORATOR",
        updated_at: datetime | None = None,
    ) -> None:
        """Issue `number` with `labels` and `body`, which may hold a record block. It has
        `sub_issues` sub-issues, which GitHub counts in each issue's `sub_issues_summary`. It is
        a sub-issue of issue `parent` of `parent_repo`, this repository by default, which GitHub
        gives in each issue's `parent_issue_url`. Its author has `author_association` with the
        repository."""
        self.issues[number] = {
            "id": number,
            "number": number,
            "title": title or f"Issue {number}",
            "html_url": f"https://github.com/{self.repo}/issues/{number}",
            "repository_url": f"https://api.github.com/repos/{self.repo}",
            "parent_issue_url": (
                None
                if parent is None
                else f"https://api.github.com/repos/{parent_repo or self.repo}/issues/{parent}"
            ),
            "body": body,
            "state": state,
            "labels": [{"name": label} for label in labels],
            "milestone": self._milestone(milestone),
            "node_id": f"I_{number}",
            "author_association": author_association,
            "created_at": "2026-10-01T00:00:00Z",
            "updated_at": _wire(updated_at or datetime(2026, 10, 2, tzinfo=UTC)),
            "sub_issues_summary": {"total": sub_issues, "completed": 0, "percent_completed": 0},
        }
        if pull_request:
            self.issues[number]["pull_request"] = {
                "url": f"https://api.github.com/repos/{self.repo}/pulls/{number}",
                "html_url": f"https://github.com/{self.repo}/pull/{number}",
            }

    def seed_pull(
        self,
        number: int,
        title: str = "",
        *,
        head_ref: str,
        draft: bool = False,
        state: str = "open",
        updated_at: datetime | None = None,
    ) -> None:
        """Pull request `number` on branch `head_ref`: its issue, and its entry in the pull
        request listing."""
        self.seed_issue(number, title, state=state, pull_request=True, updated_at=updated_at)
        self.pulls[number] = {
            "number": number,
            "title": title or f"Pull request {number}",
            "html_url": f"https://github.com/{self.repo}/pull/{number}",
            "state": state,
            "draft": draft,
            "head": {"ref": head_ref, "sha": "0" * 40},
            "updated_at": self.issues[number]["updated_at"],
        }

    def seed_label(self, name: str, color: str, description: str | None = "") -> None:
        """A label of the repository; GitHub gives a missing description as null."""
        self.label_catalog.append({"name": name, "color": color, "description": description})

    def seed_repository(
        self, repository: dict[str, Any], release: dict[str, Any] | None = None
    ) -> None:
        """Another repository, by the `full_name` of its REST payload, and its latest release,
        which GitHub answers 404 when there is none (#2650)."""
        self.repositories[repository["full_name"]] = (repository, release)

    def labels(self, number: int) -> list[str]:
        """The labels issue `number` holds now."""
        return [label["name"] for label in self.issues[number]["labels"]]

    def body(self, number: int) -> str:
        """The body issue `number` holds now, its record block included."""
        return str(self.issues[number]["body"] or "")

    def project_calls(self) -> list[list[str]]:
        """Every request sent that names a project board or `.github/roadmap.toml`."""
        return [
            args
            for args in self.calls
            if args[0] == "project" or any(word in " ".join(args) for word in PROJECT_WORDS)
        ]

    def traffic_calls(self) -> list[str]:
        """The path of every traffic request sent, in order."""
        return [
            arg
            for args in self.calls
            for arg in args[1:]
            if arg.startswith("repos/") and "/traffic/" in arg
        ]

    def writes(self) -> list[list[str]]:
        """Every request sent that writes: a `-X` other than GET."""
        return [args for args in self.calls if "-X" in args and args[args.index("-X") + 1] != "GET"]

    # ── The process edge ──

    def __call__(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        self.stdins.append(kwargs.get("input"))
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
        if args[0].startswith(f"{API}/"):
            return self._listing(args[0].removeprefix(f"{API}/"))
        assert args[0] == "api", f"not a gh command the store sends: {args}"
        if args[1] == "graphql":
            return self._graphql(args)
        if args[1] == "user":
            return f"{self.login}\n"
        if args[1] == "rate_limit":
            reset = int(time.time()) + 60
            quota = {"limit": 5000, "remaining": 5000, "used": 0, "reset": reset}
            return {"resources": {name: quota for name in ("core", "graphql", "search")}}
        return self._rest(args, stdin)

    def _graphql(self, args: list[str]) -> Any:
        query = gh_variables(args).get("query", "")
        if "timelineItems" in query:
            connection = {"totalCount": 0, "nodes": []}
            return {"data": {"repository": {"issue": {"timelineItems": connection}}}}
        if "isPrivate" in query:
            return {"data": {"repository": {"isPrivate": False}}}
        raise AssertionError(f"no fake for the GraphQL request: {query[:120]}")

    # ── REST ──

    def _listing(self, path: str) -> Any:
        """A REST listing the store reads through its session (`RunnerSession`, #983): every
        page, as the session follows GitHub's links, or the first failed one."""
        per_page = int(parse_qs(urlsplit(path).query).get("per_page", ["30"])[0])
        listing: list[Any] = []
        page = 1
        while True:
            entries = self._rest(["api", f"{path}&page={page}"], None)
            if not isinstance(entries, list):
                return entries
            listing += entries
            if len(entries) < per_page:
                return listing
            page += 1

    def _rest(self, args: list[str], stdin: str | None) -> Any:
        method = args[args.index("-X") + 1] if "-X" in args else "GET"
        path = next(arg for arg in args[1:] if "/" in arg and not arg.startswith(("-", "Accept")))
        fields = dict(
            args[index + 1].split("=", 1)
            for index, arg in enumerate(args)
            if arg in ("-f", "-F") and "=" in args[index + 1]
        )
        url = urlsplit(path)
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        other = self._other_repository(url.path)
        if other is not None:
            return other
        if url.path == f"repos/{self.repo}":
            open_issues = sum(issue["state"] == "open" for issue in self.issues.values())
            return {"stargazers_count": 0, "forks_count": 0, "open_issues_count": open_issues}
        parts = url.path.removeprefix(f"repos/{self.repo}/").split("/")
        if "--paginate" in args:
            return self._paginate_rest(method, parts, query, fields, args)
        return self._route(method, parts, query, fields, args, stdin)

    def _other_repository(self, path: str) -> Any:
        """The answer for a repository seeded with `seed_repository`, or its latest release, or
        None when `path` names neither."""
        name = path.removeprefix("repos/")
        if name in self.repositories:
            return self.repositories[name][0]
        name = name.removesuffix("/releases/latest")
        if name != path.removeprefix("repos/") and name in self.repositories:
            release = self.repositories[name][1]
            return release if release is not None else (1, "gh: Not Found (HTTP 404)")
        return None

    def _paginate_rest(
        self,
        method: str,
        parts: list[str],
        query: dict[str, str],
        fields: dict[str, str],
        args: list[str],
    ) -> Any:
        per_page = int(query.get("per_page", "100"))
        pages: list[Any] = []
        page = 1
        while True:
            entries = self._route(method, parts, {**query, "page": str(page)}, fields, args, None)
            if not isinstance(entries, list):
                return entries
            pages.append(entries)
            if len(entries) < per_page:
                break
            page += 1
        return "".join(json.dumps(p) for p in pages)

    def _route(
        self,
        method: str,
        parts: list[str],
        query: dict[str, str],
        fields: dict[str, str],
        args: list[str],
        stdin: str | None,
    ) -> Any:
        page = int(query.get("page", "1"))
        if parts[0] == "contents":
            name = unquote("/".join(parts[1:]))
            return self.files[name] if name in self.files else (1, "gh: Not Found (HTTP 404)")
        if parts[0] == "commits":
            return {"sha": parts[1]} if parts[1] in self.commits else (1, "HTTP 422")
        if "/".join(parts) == "issues/events":
            size = int(query.get("per_page", "100"))
            return self.events[(page - 1) * size : page * size]
        if parts == ["actions", "runs"]:
            return {"total_count": 0, "workflow_runs": []}
        if parts[0] == "traffic" and self.traffic_answer is not None:
            return self.traffic_answer
        if parts[0] == "traffic":
            return [] if parts[1] == "popular" else {"count": 0, "uniques": 0}
        if parts[0] == "milestones":
            return self.milestones if page == 1 else []
        if parts[0] in ("pulls", "labels"):
            return self._catalog(parts[0], query, page)
        if parts == ["issues"]:
            labels = [arg.split("=", 1)[1] for arg in args if arg.startswith("labels[]=")]
            return self._issues(method, query, fields | {"labels": json.dumps(labels)}, page)
        return self._issue_route(method, int(parts[1]), parts[2:], fields, page, stdin)

    def _catalog(self, kind: str, query: dict[str, str], page: int) -> list[dict[str, Any]]:
        """A page of the pull request listing, the open ones by default, or of the labels."""
        listed = (
            list(self.label_catalog)
            if kind == "labels"
            else [
                pull
                for pull in self.pulls.values()
                if query.get("state", "open") in ("all", pull["state"])
            ]
        )
        per_page = int(query.get("per_page", "30"))
        return listed[(page - 1) * per_page : page * per_page]

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
        per_page = int(query.get("per_page", "100"))
        return listed[(page - 1) * per_page : page * per_page]

    def _issue_route(
        self,
        method: str,
        number: int,
        rest: list[str],
        fields: dict[str, str],
        page: int,
        stdin: str | None,
    ) -> Any:
        if number not in self.issues:
            return (1, "gh: Not Found (HTTP 404)")
        issue = self.issues[number]
        if rest == ["labels"]:
            if fields["labels[]"] not in self.labels(number):
                issue["labels"].append({"name": fields["labels[]"]})
            return issue["labels"]
        if rest == ["comments"] and method == "POST":
            self.comments.setdefault(number, []).append(fields["body"])
            return {}
        if rest == ["sub_issues"] and method == "POST":
            sub_id = int(fields["sub_issue_id"])
            child = next(
                (i for i in self.issues.values() if i.get("id") == sub_id or i["number"] == sub_id),
                None,
            )
            if child is None:
                return (1, "gh: Not Found (HTTP 404)")
            issue["sub_issues_summary"]["total"] += 1
            child["parent_issue_url"] = f"https://api.github.com/repos/{self.repo}/issues/{number}"
            return child
        if rest == ["comments"]:
            bodies = self.comments.get(number, []) if page == 1 else []
            return [{"body": body, "created_at": "2026-10-01T00:00:00Z"} for body in bodies]
        if method == "PATCH":
            self._edit(issue, json.loads(stdin) if stdin else fields)
        return issue

    @staticmethod
    def _edit(issue: dict[str, Any], fields: Mapping[str, Any]) -> None:
        """Apply an issue `PATCH`: `labels` replaces the labels, `body` the body, and `state`
        and `state_reason` the state and the reason of a close."""
        for name in ("state", "state_reason"):
            if name in fields:
                issue[name] = fields[name]
        if "labels" in fields:
            issue["labels"] = [{"name": label} for label in fields["labels"]]
        if "body" in fields:
            issue["body"] = fields["body"]

    def close(self, number: int, reason: str) -> None:
        """Close issue `number` for `reason`."""
        self.issues[number].update(state="closed", state_reason=reason)

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


def _wire(moment: datetime) -> str:
    """A moment as GitHub writes it in a payload."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
