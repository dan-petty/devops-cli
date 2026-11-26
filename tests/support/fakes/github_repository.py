"""A fake GitHub repository answering the roadmap store's `gh` commands (#1125, #1361, #2399).

`GitHubFake` is a whole repository at the `gh` process edge: REST issues, with their labels and
bodies, milestones, comments, events and files, each write applied to what later reads return.
It answers `PATCH` of an issue with its fields as JSON on stdin (`--input -`), as `gh api` sends
them: `labels` replaces the issue's labels and `body` its body. It also answers the project
metrics reads (the repository, its Actions runs and its traffic), the hooks of the repository and
the deliveries of each hook (#5017), `gh api user` with its `login`,
and `gh api rate_limit` with a full quota that resets in a minute. It keeps every argv, and
`project_calls` gives each one that names a project board, so a test shows that a roadmap job
sends none. Neither starts `gh` nor opens a socket. `GitHubFake.process` stands in for
`subprocess.run` itself, answering `gh` and passing every other program, such as `git`, to the
real one. `GitHubFake.serve_session` answers the GETs of a GitHub session for the repository
through the `web` fake in the same way.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

import httpx2

from devops_cli.config.constants import CONST_GH_CLI
from tests.support.fakes.github import API
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

if TYPE_CHECKING:
    from tests.support.fakes.http import WebFake

PROJECT_WORDS = ("projectV2", "ProjectV2", "roadmap.toml")
"""What a GraphQL request that reads or writes a project board, or a read of the old roadmap
file, names; a `gh project` command is one too."""


def _writes(args: list[str]) -> bool:
    """Whether the request writes: a `-X` other than GET."""
    return "-X" in args and args[args.index("-X") + 1] != "GET"


def gh_variables(args: list[str]) -> dict[str, str]:
    """The `-f`/`-F` fields of a `gh api graphql` argv, by name."""
    pairs = (args[i + 1] for i, arg in enumerate(args) if arg in ("-f", "-F"))
    return dict(pair.split("=", 1) for pair in pairs)


class GitHubFake:
    """One repository's issues and milestones, answering the store's `gh` commands.

    `issues` maps a number to its REST payload. `files` maps a path to its text, or to the
    `(exit code, output)` `gh` gives for it, such as a 502. `traffic_answer`, when set, is the
    `(exit code, output)` that `gh` gives for every traffic path, such as the 403 that an
    installation token gets (#2752). `hooks_answer`, when set, is the `(exit code, output)` that
    `gh` gives for the hooks of the repository, such as the 403 of a token with no Webhooks
    permission (#5017).
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
        self.hooks_answer: tuple[int, str] | None = None
        self.hooks: dict[int, tuple[bool, list[dict[str, Any]]]] = {}
        # The answers that the first reads of the deliveries of a hook get, in turn, before the
        # seeded deliveries, and the next page that the last read of deliveries links (#6012).
        self.deliveries_answers: list[tuple[int, str]] = []
        # The next page that an answer of `deliveries_answers` links, such as one on another host.
        self.deliveries_answer_link: str | None = None
        self._next_link: str | None = None
        self.milestones = list(milestones)
        self.files = dict(files or {})
        self.events = list(events)
        self.commits = set(commits)
        self.check_runs: dict[str, list[dict[str, str]]] = {}
        self.issues: dict[int, dict[str, Any]] = {}
        # The issues that left the repository, by the number they had here (`move_issue`).
        self.moved: dict[int, dict[str, Any]] = {}
        self.pulls: dict[int, dict[str, Any]] = {}
        self.label_catalog: list[dict[str, Any]] = []
        self.comments: dict[int, list[str]] = {}
        self.blockers: dict[int, list[int]] = {}
        self.releases: list[dict[str, Any]] = []
        self.repositories: dict[str, tuple[dict[str, Any], dict[str, Any] | None]] = {}
        # The package URLs of the SBOM that the dependency graph of the repository exports.
        self.purls: list[str] = []
        self.calls: list[list[str]] = []
        self.stdins: list[str | None] = []
        self._fault_at = 0
        self._fault_applied = False

    # ── Seeding ──

    def seed_comment(self, number: int, body: str) -> dict[str, Any]:
        """A comment on issue `number`, which GitHub counts in the `comments` of its listing. It
        gives the comment as GitHub gives it."""
        self.comments.setdefault(number, []).append(body)
        self.issues[number]["comments"] = len(self.comments[number])
        return self._comment_payload(number, len(self.comments[number]) - 1)

    def _comment_payload(self, number: int, index: int) -> dict[str, Any]:
        """Comment `index` of issue `number` as GitHub gives it: its id, body, time and page.
        A comment on a pull request has its page under `pull/`."""
        made_id = number * 1000 + index + 1
        kind = "pull" if self.issues[number].get("pull_request") else "issues"
        return {
            "id": made_id,
            "body": self.comments[number][index],
            "created_at": "2026-10-01T00:00:00Z",
            "html_url": f"https://github.com/{self.repo}/{kind}/{number}#issuecomment-{made_id}",
        }

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
        author_login: str | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """Issue `number` with `labels` and `body`, which may hold a record block. It has
        `sub_issues` sub-issues, which GitHub counts in each issue's `sub_issues_summary`. It is
        a sub-issue of issue `parent` of `parent_repo`, this repository by default, which GitHub
        gives in each issue's `parent_issue_url`. Its author has `author_association` with the
        repository and the login `author_login`, which GitHub gives in `user.login`."""
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
            "user": None if author_login is None else {"login": author_login},
            "created_at": "2026-10-01T00:00:00Z",
            "updated_at": _wire(updated_at or datetime(2026, 10, 2, tzinfo=UTC)),
            "comments": 0,
            "sub_issues_summary": {"total": sub_issues, "completed": 0, "percent_completed": 0},
            "issue_dependencies_summary": {
                "blocked_by": 0,
                "blocking": 0,
                "total_blocked_by": 0,
                "total_blocking": 0,
            },
        }
        if pull_request:
            self.issues[number]["pull_request"] = {
                "url": f"https://api.github.com/repos/{self.repo}/pulls/{number}",
                "html_url": f"https://github.com/{self.repo}/pull/{number}",
            }

    def move_issue(self, number: int, *, to: str, as_number: int) -> None:
        """Transfer issue `number` to the repository `to`, where it is issue `as_number`. The
        listings of this repository give it no more. A request of the issue by the number it had
        here answers with the issue at its new place and writes nothing, as `gh` follows the
        redirect of GitHub with a read. Its comments and its events answer 404, and so does each
        other request below that number in this fake."""
        issue = self.issues.pop(number)
        self.moved[number] = {
            **issue,
            "number": as_number,
            "html_url": f"https://github.com/{to}/issues/{as_number}",
            "repository_url": f"https://api.github.com/repos/{to}",
        }

    def block(self, blocked: int, blocker: int) -> None:
        """Issue `blocker` blocks issue `blocked`. GitHub counts it in the `blocked_by` summary
        of `blocked`, and lists it at `dependencies/blocked_by` (#1127)."""
        held = self.blockers.setdefault(blocked, [])
        held.append(blocker)
        summary = self.issues[blocked]["issue_dependencies_summary"]
        summary["blocked_by"] = summary["total_blocked_by"] = len(held)

    def seed_check_run(self, sha: str, name: str, *, conclusion: str) -> None:
        """A completed check run of the commit `sha` that ended with `conclusion`."""
        self.check_runs.setdefault(sha, []).append(
            {"name": name, "status": "completed", "conclusion": conclusion}
        )

    def seed_pull(
        self,
        number: int,
        title: str = "",
        *,
        head_ref: str,
        draft: bool = False,
        state: str = "open",
        updated_at: datetime | None = None,
        head_sha: str = "0" * 40,
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
            "head": {"ref": head_ref, "sha": head_sha},
            "updated_at": self.issues[number]["updated_at"],
        }

    def seed_release(
        self,
        tag: str,
        body: str,
        published_at: datetime,
        *,
        draft: bool = False,
        prerelease: bool = False,
    ) -> None:
        """Release `tag` with the changelog `body`, published at `published_at`. The listing of
        `releases` gives the seeded ones newest first, as GitHub does."""
        self.releases.append(
            {
                "tag_name": tag,
                "html_url": f"https://github.com/{self.repo}/releases/tag/{tag}",
                "body": body,
                "published_at": _wire(published_at),
                "draft": draft,
                "prerelease": prerelease,
            }
        )

    def seed_label(self, name: str, color: str, description: str | None = "") -> None:
        """A label of the repository; GitHub gives a missing description as null."""
        self.label_catalog.append({"name": name, "color": color, "description": description})

    def seed_repository(
        self, repository: dict[str, Any], release: dict[str, Any] | None = None
    ) -> None:
        """Another repository, by the `full_name` of its REST payload, and its latest release,
        which GitHub answers 404 when there is none (#2650)."""
        self.repositories[repository["full_name"]] = (repository, release)

    def seed_dependencies(self, *purls: str) -> None:
        """Add `purls` to the SPDX SBOM that `dependency-graph/sbom` exports (#4661)."""
        self.purls.extend(purls)

    def seed_hook(
        self, hook_id: int, deliveries: Iterable[dict[str, Any]] = (), *, active: bool = True
    ) -> None:
        """Webhook `hook_id` of the repository and its deliveries, newest first, as GitHub
        lists them at `hooks/<id>/deliveries` (#5017)."""
        self.hooks[hook_id] = (active, list(deliveries))

    def hook_calls(self) -> list[str]:
        """The path of every request sent for the hooks or their deliveries, in order."""
        return [
            arg
            for args in self.calls
            for arg in args[1:]
            if arg.startswith(f"repos/{self.repo}/hooks")
        ]

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
        return [args for args in self.calls if _writes(args)]

    def fail_write(self, *, at: int = 1, applied: bool = False) -> None:
        """Fail one request that writes, as `gh` fails part-way through a run: the `at`-th write
        from now, counted from 1, answers a 502 once. With `applied`, GitHub applied the write
        and the answer still reports the failure, so the change stays in place."""
        self._fault_at = len(self.writes()) + at
        self._fault_applied = applied

    # ── The process edge ──

    def __call__(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        self.stdins.append(kwargs.get("input"))
        reply: Any
        if _writes(args) and len(self.writes()) == self._fault_at:
            self._fault_at = 0
            if self._fault_applied:
                self._answer(args, kwargs.get("input"))
            reply = (1, "gh: HTTP 502 (HTTP 502)")
        else:
            reply = self._answer(args, kwargs.get("input"))
        returncode, output = reply if isinstance(reply, tuple) else (0, reply)
        text = output if isinstance(output, str) else json.dumps(output)
        if "--include" in args and returncode == 0:
            link = "" if self._next_link is None else f'Link: <{self._next_link}>; rel="next"\r\n'
            text = f"HTTP/2.0 200 OK\r\nContent-Type: application/json\r\n{link}\r\n{text}"
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

    def answer_children(self, monkeypatch: Any) -> None:
        """Answer each `gh` child of the real process runner as this fake, and hand every other
        program to the real call: through `subprocess.run`, and through `_run_in_own_session`,
        which starts a child that gets the session's token."""
        from devops_cli.core import process

        monkeypatch.setattr(subprocess, "run", self.process(subprocess.run))
        monkeypatch.setattr(
            process, "_run_in_own_session", self.process(process._run_in_own_session)
        )

    def install(self, fake: ProcessFake) -> None:
        """Answer each `gh` command that `fake` is asked to run as this repository, and leave
        every other program to the answers of `fake`."""

        def is_gh(call: ProcessCall) -> bool:
            return bool(call.argv) and Path(call.argv[0]).name == CONST_GH_CLI

        def answer(call: ProcessCall) -> ProcessAnswer:
            stdin = call.stdin if isinstance(call.stdin, str) else None
            done = self(list(call.argv[1:]), input=stdin)
            return ProcessAnswer(returncode=done.returncode, stdout=done.stdout, stderr=done.stderr)

        fake.answer(is_gh, answer)

    def serve_session(self, web: WebFake) -> None:
        """Answer each GET that a GitHub session sends through `web` for this repository as this
        fake answers the same path through gh, so a reader that moved from gh to the session
        (#3941) reads the same repository. A failed answer is not served: `web` gives its own."""
        prefix = f"{API}/repos/{self.repo}/"

        def answer(request: httpx2.Request) -> httpx2.Response | None:
            url = str(request.url)
            if request.method != "GET" or not url.startswith(prefix):
                return None
            done = self(["api", url.removeprefix(f"{API}/")])
            if done.returncode != 0:
                return None
            return httpx2.Response(200, json=json.loads(done.stdout))

        web.serve(answer)

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
        if url.path == f"repos/{self.repo}/dependency-graph/sbom":
            return self._sbom()
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

    def _sbom(self) -> Any:
        """The SPDX SBOM of the repository, with one package for each seeded package URL."""
        packages = [
            {"externalRefs": [{"referenceType": "purl", "referenceLocator": purl}]}
            for purl in self.purls
        ]
        return {"sbom": {"spdxVersion": "SPDX-2.3", "packages": packages}}

    def _commit_route(self, parts: list[str]) -> Any:
        """The check runs of a commit, or the commit itself when the fake holds it."""
        if parts[-1:] == ["check-runs"]:
            runs = self.check_runs.get(parts[1], [])
            return {"total_count": len(runs), "check_runs": runs}
        return {"sha": parts[1]} if parts[1] in self.commits else (1, "HTTP 422")

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
            return self._commit_route(parts)
        if "/".join(parts) == "issues/events":
            size = int(query.get("per_page", "100"))
            return self.events[(page - 1) * size : page * size]
        if parts == ["actions", "runs"]:
            return {"total_count": 0, "workflow_runs": []}
        if parts[0] == "traffic":
            return self._traffic_route(parts)
        if parts[0] == "milestones":
            return self.milestones if page == 1 else []
        if parts[0] == "hooks":
            return self._hooks_route(parts, query)
        if parts[0] in ("pulls", "labels", "releases"):
            return self._catalog(parts[0], query, page)
        if parts == ["issues"]:
            labels = [arg.split("=", 1)[1] for arg in args if arg.startswith("labels[]=")]
            return self._issues(method, query, fields | {"labels": json.dumps(labels)}, page)
        return self._issue_route(method, int(parts[1]), parts[2:], fields, page, stdin)

    def _traffic_route(self, parts: list[str]) -> Any:
        """A traffic path of the repository: `traffic_answer` when set, else no traffic."""
        if self.traffic_answer is not None:
            return self.traffic_answer
        return [] if parts[1] == "popular" else {"count": 0, "uniques": 0}

    def _hooks_route(self, parts: list[str], query: dict[str, str]) -> Any:
        """The hooks of the repository, or one page of the deliveries of one hook: `per_page`
        of them from the offset that `cursor` names, only the failed ones for `status=failure`,
        with the next page as the link of the answer while more are left (#6012)."""
        self._next_link = None
        if parts == ["hooks"]:
            if self.hooks_answer is not None:
                return self.hooks_answer
            return [{"id": key, "active": active} for key, (active, _) in self.hooks.items()]
        hook = self.hooks.get(int(parts[1]))
        if hook is None or parts[2:] != ["deliveries"]:
            return (1, "gh: Not Found (HTTP 404)")
        if self.deliveries_answers:
            self._next_link = self.deliveries_answer_link
            return self.deliveries_answers.pop(0)
        listed = [
            delivery
            for delivery in hook[1]
            if query.get("status") != "failure" or not 200 <= delivery["status_code"] < 300
        ]
        size = int(query.get("per_page", "30"))
        start = int(query.get("cursor", "v1_0").removeprefix("v1_"))
        if start + size < len(listed):
            self._next_link = (
                f"{API}/repos/{self.repo}/hooks/{parts[1]}/deliveries"
                f"?{urlencode({**query, 'cursor': f'v1_{start + size}'})}"
            )
        return listed[start : start + size]

    def _blockers_page(self, number: int, page: int) -> list[dict[str, Any]]:
        """A page of 100 issues that block issue `number`, as GitHub lists them at
        `dependencies/blocked_by` (#1127)."""
        held = [self.issues[blocker] for blocker in self.blockers.get(number, [])]
        return held[(page - 1) * 100 : page * 100]

    def _issue_events(self, number: int, page: int) -> list[dict[str, Any]]:
        """The events of issue `number` on its own listing, a page of 100 as the store asks for:
        the seeded events of that issue, without their `issue` key, as GitHub lists them there
        (#2919)."""
        own = [
            {key: value for key, value in event.items() if key != "issue"}
            for event in self.events
            if (event.get("issue") or {}).get("number") == number
        ]
        return own[(page - 1) * 100 : page * 100]

    def _catalog(self, kind: str, query: dict[str, str], page: int) -> list[dict[str, Any]]:
        """A page of the pull request listing, the open ones by default, of the labels, or of the
        releases, newest first."""
        if kind == "releases":
            listed = sorted(self.releases, key=lambda r: r["published_at"], reverse=True)
        else:
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
        # `since` keeps the issues updated at or after it; both are written as `_wire` writes them.
        listed = [
            issue
            for issue in self.issues.values()
            if query.get("state", "open") in ("all", issue["state"])
            and self._in_milestone(issue, query.get("milestone"))
            and issue["updated_at"] >= query.get("since", "")
        ]
        if query.get("sort") == "created" and query.get("direction") == "desc":
            listed.sort(key=lambda issue: issue["number"], reverse=True)
        if query.get("sort") == "updated" and query.get("direction") == "desc":
            listed.sort(key=lambda issue: issue["updated_at"], reverse=True)
        per_page = int(query.get("per_page", "100"))
        return listed[(page - 1) * per_page : page * per_page]

    def _post_blocked_by(self, number: int, fields: dict[str, str]) -> Any:
        blocker_id = int(fields["issue_id"])
        blocker = next(
            (
                i
                for i in self.issues.values()
                if i.get("id") == blocker_id or i["number"] == blocker_id
            ),
            None,
        )
        if blocker is None:
            return (1, "gh: Not Found (HTTP 404)")
        self.block(number, blocker["number"])
        return blocker

    def _post_sub_issue(self, number: int, issue: dict[str, Any], fields: dict[str, str]) -> Any:
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

    def _issue_route(
        self,
        method: str,
        number: int,
        rest: list[str],
        fields: dict[str, str],
        page: int,
        stdin: str | None,
    ) -> Any:
        if number in self.moved:
            return (1, "gh: Not Found (HTTP 404)") if rest else self.moved[number]
        listings = {"events": self._issue_events, "dependencies/blocked_by": self._blockers_page}
        if (
            method == "GET"
            and (listing := listings.get("/".join(rest))) is not None
            and (number in self.issues or rest == ["events"])
        ):
            return listing(number, page)
        if number not in self.issues:
            return (1, "gh: Not Found (HTTP 404)")
        return self._held_issue_route(method, number, rest, fields, page, stdin)

    def _held_issue_route(
        self,
        method: str,
        number: int,
        rest: list[str],
        fields: dict[str, str],
        page: int,
        stdin: str | None,
    ) -> Any:
        """The answer of a request of issue `number`, which the repository holds, or below it."""
        issue = self.issues[number]
        if rest == ["dependencies", "blocked_by"] and method == "POST":
            return self._post_blocked_by(number, fields)
        if rest == ["labels"]:
            if fields["labels[]"] not in self.labels(number):
                issue["labels"].append({"name": fields["labels[]"]})
            return issue["labels"]
        if rest == ["comments"] and method == "POST":
            return self.seed_comment(number, fields["body"])
        if rest == ["sub_issues"] and method == "POST":
            return self._post_sub_issue(number, issue, fields)
        if rest == ["comments"]:
            held = range(len(self.comments.get(number, []))) if page == 1 else range(0)
            return [self._comment_payload(number, index) for index in held]
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
