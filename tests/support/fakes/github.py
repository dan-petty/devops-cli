"""GitHub's REST API faked at the HTTP edge for the GitHub session, and the `github_api` fixture
that installs it (#983, ADR 0007).

`GitHubApiFake` answers the session's requests through httpx2's own `MockTransport`, reached the
way `stub_web` reaches canned pages: `client_class()` is an `httpx2.AsyncClient` that keeps
everything the factory gave it except the transport. The factory, its timeouts and the session's
options stay real, so the session's client follows redirects and runs its origin hook exactly as
it does against GitHub, gidgethub decodes each answer as it decodes GitHub's, and every request's
host is still vetted at the egress level the factory built the client for. The `github_api`
fixture installs it for the process's session.

A route answers with its responses in order, and its last response repeats. A response may be an
`httpx2.TransportError` class, which is raised for the request instead, as a refused connect is.
A request whose `If-None-Match` names the ETag of the response it would get gets a 304 instead,
with that response's headers but no body and no `Link`, as GitHub answers one. A request no
route names gets GitHub's 404. GitHub reports the identity's quota as it stands with every REST
answer; a 304 spends none of it and a 404 spends one. So the fake holds, in `quota`, the quota it
last reported for each resource, which a test may also set: its own 304 reports it, and its own
404 spends one from it and reports what is left. With `delay` set, each answer arrives that many
seconds after its request, so requests can be in flight together. The fake records every request
it receives, each client it answers and that client's egress level, the pauses the rate limiter
asked for and the waits gidgethub's retry hook asked for; neither takes any time.

The fake's contract suite, `tests/test_github_contract.py`, runs each case through the session
over the fake and over `RecordedGitHubApi`, which answers with GitHub's own answers, recorded on
2026-10-19, in the order they were recorded, and fails the test on any request whose method, URL,
`If-None-Match` or body is not the one recorded next. `serve_github_api` installs either one; the
`github_api` fixture installs the fake, and refuses any gh command the rate limiter would run
(`run_gh` and the quota refresh).

`pull_request_payload`, `pull_request_file_payload`, `route_pull_request`, `route_file` and
`route_merge_base` give a test a pull request to read: the fields devops-cli reads of one, and the
routes that answer the reads a review or an analysis makes of it (#891).

`RunnerSession` is a session whose listings a scripted gh runner answers, for the roadmap store
tests that script gh for the board as well.
"""

from __future__ import annotations

import base64
import json
import subprocess
import time
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping, Sequence
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from typing import Any, NoReturn
from urllib.parse import quote, urlencode

import anyio
import httpx2
import pytest

from devops_cli.config.constants import CONST_GITHUB_DIFF_MEDIA_TYPE
from devops_cli.http.egress import EgressLevel
from tests.web_fakes import egress_level_of, install_async_client_fake, vetted_handler

API = "https://api.github.com"
JSON_TYPE = "application/json; charset=utf-8"
_QUOTA_REMAINING = "x-ratelimit-remaining"
_QUOTA_USED = "x-ratelimit-used"
_QUOTA_RESOURCE = "x-ratelimit-resource"
_QUOTA_HEADERS = (
    "x-ratelimit-limit",
    _QUOTA_REMAINING,
    "x-ratelimit-reset",
    _QUOTA_USED,
    _QUOTA_RESOURCE,
)

Answer = httpx2.Response | type[httpx2.TransportError]


def github_json(
    payload: Any = None, *, status: int = 200, headers: dict[str, str] | None = None
) -> httpx2.Response:
    """A response with a JSON body, as GitHub's REST API answers."""
    body = b"" if payload is None else json.dumps(payload).encode()
    return httpx2.Response(
        status, headers={"content-type": JSON_TYPE, **(headers or {})}, content=body
    )


def github_text(
    text: str, *, media_type: str, status: int = 200, headers: dict[str, str] | None = None
) -> httpx2.Response:
    """A response whose body is `text` of `media_type`, as a diff is served."""
    return httpx2.Response(
        status,
        headers={"content-type": f"{media_type}; charset=utf-8", **(headers or {})},
        content=text.encode(),
    )


def github_redirect(location: str, *, status: int = 301) -> httpx2.Response:
    """A redirect to `location`, which may be relative."""
    return httpx2.Response(status, headers={"location": location})


def next_page(url: str) -> dict[str, str]:
    """The `Link` header GitHub sends with a page that has a next one, at `url` (or a path under
    the API), beside the link to the last page."""
    target = httpx2.URL(API).join(url)
    return {"link": f'<{target}>; rel="next", <{target.copy_with(query=b"page=99")}>; rel="last"'}


def quota_headers(
    remaining: int, *, resource: str = "core", limit: int = 5000, reset_in: float = 600.0
) -> dict[str, str]:
    """The rate-limit headers GitHub sends with every REST answer."""
    return {
        "x-ratelimit-limit": str(limit),
        "x-ratelimit-remaining": str(remaining),
        "x-ratelimit-reset": str(int(time.time() + reset_in)),
        "x-ratelimit-used": str(limit - remaining),
        "x-ratelimit-resource": resource,
    }


def pull_request_payload(
    *,
    title: str = "Change the app",
    head_sha: str = "abc123",
    head_repo: str | None = "fork/app",
    base_sha: str = "base456",
    base_repo: str = "base/app",
    base_ref: str = "main",
) -> dict[str, Any]:
    """A pull request as GitHub sends it, cut to the fields devops-cli reads. A `head_repo` of
    None is the head of a pull request whose fork was deleted: GitHub sends `repo` as null."""
    head: dict[str, Any] = {
        "sha": head_sha,
        "ref": "feature",
        "repo": None if head_repo is None else {"full_name": head_repo},
    }
    base = {"sha": base_sha, "ref": base_ref, "repo": {"full_name": base_repo}}
    return {"title": title, "head": head, "base": base}


def pull_request_file_payload(
    filename: str,
    status: str = "modified",
    *,
    previous_filename: str | None = None,
    additions: int = 1,
    changes: int = 1,
) -> dict[str, Any]:
    """One entry of `GET /repos/{repo}/pulls/{n}/files`; `previous_filename` is sent for a
    renamed file only."""
    entry: dict[str, Any] = {
        "filename": filename,
        "status": status,
        "additions": additions,
        "changes": changes,
    }
    if previous_filename is not None:
        entry["previous_filename"] = previous_filename
    return entry


def route_pull_request(
    api: GitHubApiFake,
    repo: str,
    number: int,
    pull: Mapping[str, Any],
    *,
    files: Sequence[Mapping[str, Any]] = (),
    diff: str = "",
) -> None:
    """Answer the reads of one pull request: `pull` and then `diff` at its URL, as the object is
    read before the diff, and `files` as the one page of its files."""
    path = f"/repos/{repo}/pulls/{number}"
    api.route(
        "GET",
        path,
        github_json(pull),
        github_text(diff, media_type=CONST_GITHUB_DIFF_MEDIA_TYPE),
    )
    api.route("GET", f"{path}/files?per_page=100", github_json(list(files)))


def route_file(api: GitHubApiFake, repo: str, path: str, ref: str, text: str) -> None:
    """Answer the read of `path` at `ref` in `repo` with `text`, as the contents endpoint does."""
    content = base64.encodebytes(text.encode()).decode()
    api.route(
        "GET",
        f"/repos/{repo}/contents/{quote(path, safe='/')}?{urlencode({'ref': ref})}",
        github_json({"type": "file", "encoding": "base64", "content": content}),
    )


def route_merge_base(api: GitHubApiFake, repo: str, base: str, head: str, sha: str) -> None:
    """Answer the comparison of `base` and `head` in `repo` with `sha` as their merge base."""
    api.route(
        "GET",
        f"/repos/{repo}/compare/{base}...{head}?per_page=1",
        github_json({"merge_base_commit": {"sha": sha}}),
    )


class PacedClock:
    """The `time` module as the rate limiter reads it, except that a pause is recorded in `paced`
    instead of slept, so a test paces without waiting and nothing else's sleep changes."""

    def __init__(self, paced: list[float]) -> None:
        self.sleep = paced.append

    def __getattr__(self, name: str) -> Any:
        return getattr(time, name)


class GitHubApiDouble:
    """What the fake and the recorded API share: the client class that reaches them, and the
    record of every request each receives, each client it answers and that client's egress level,
    and the pauses and retry waits that took no time."""

    def __init__(self) -> None:
        self.sent: list[httpx2.Request] = []
        self.levels: list[EgressLevel | None] = []
        self.clients: list[httpx2.AsyncClient] = []
        self.paced: list[float] = []
        self.waits: list[float] = []
        self.delay = 0.0

    @property
    def requested(self) -> list[str]:
        """Each request's method and URL, in the order they were received."""
        return [f"{request.method} {request.url}" for request in self.sent]

    def client_class(self) -> type[httpx2.AsyncClient]:
        """An `httpx2.AsyncClient` that answers from this API in place of the transport it was
        given, after vetting each request at that transport's egress level."""
        api = self

        class GitHubApiClient(httpx2.AsyncClient):
            fake_owner = "github_api"

            def __init__(self, **kwargs: Any) -> None:
                level = egress_level_of(kwargs.get("transport"))
                api.levels.append(level)
                transport = httpx2.MockTransport(vetted_handler(api._handle, level))
                super().__init__(**{**kwargs, "transport": transport})
                api.clients.append(self)

        return GitHubApiClient

    async def wait(self, seconds: float) -> None:
        """Stand in for gidgethub's `sleep`: record the retry wait and return at once."""
        self.waits.append(seconds)

    def _handle(self, request: httpx2.Request) -> httpx2.Response | Awaitable[httpx2.Response]:
        """Record `request` and give it its answer, `delay` seconds later."""
        self.sent.append(request)
        response = self._answer(request)
        return self._later(response) if self.delay else response

    def _answer(self, request: httpx2.Request) -> httpx2.Response:
        raise NotImplementedError

    async def _later(self, response: httpx2.Response) -> httpx2.Response:
        await anyio.sleep(self.delay)
        return response


class GitHubApiFake(GitHubApiDouble):
    """GitHub's REST API, answered from routes, recording every request it receives."""

    def __init__(self) -> None:
        super().__init__()
        self._routes: dict[tuple[str, str], list[Answer]] = {}
        # The rate-limit headers the fake last reported, by resource: what its own answers report.
        self.quota: dict[str, dict[str, str]] = {}

    def route(self, method: str, url: str, *answers: Answer) -> None:
        """Answer `method` on `url` (absolute, or a path under the API) with `answers` in turn."""
        self._routes[(method, str(httpx2.URL(API).join(url)))] = list(answers)

    def _answer(self, request: httpx2.Request) -> httpx2.Response:
        answers = self._routes.get((request.method, str(request.url)))
        if not answers:
            return self._not_found(request)
        answer = answers.pop(0) if len(answers) > 1 else answers[0]
        if isinstance(answer, type):
            raise answer("connection refused", request=request)
        if answer.status_code != HTTPStatus.NOT_MODIFIED and _names_the_etag_of(request, answer):
            return _not_modified(answer, self.quota.get(_resource_of(answer.headers), {}))
        self._hold_quota(answer.headers)
        return httpx2.Response(answer.status_code, headers=answer.headers, content=answer.content)

    def _hold_quota(self, headers: httpx2.Headers) -> None:
        """Hold the quota an answer reports as the one GitHub reports next for its resource."""
        if _QUOTA_REMAINING in headers:
            held = {name: headers[name] for name in _QUOTA_HEADERS if name in headers}
            self.quota[_resource_of(headers)] = held

    def _not_found(self, request: httpx2.Request) -> httpx2.Response:
        """GitHub's 404, which spends one from the quota held for the resource the session paces
        `request` on, and reports what is left."""
        from devops_cli.github.rate_limiter import gh_request_resource

        resource = gh_request_resource(["api", request.url.path])
        held = self.quota.get(resource)
        if held is not None:
            held = self.quota[resource] = _spent_one(held)
        return github_json({"message": "Not Found"}, status=404, headers=held)


def _spent_one(quota: Mapping[str, str]) -> dict[str, str]:
    """`quota` with one request more spent: one less remaining, one more used."""
    spent = dict(quota)
    spent[_QUOTA_REMAINING] = str(int(quota[_QUOTA_REMAINING]) - 1)
    if _QUOTA_USED in quota:
        spent[_QUOTA_USED] = str(int(quota[_QUOTA_USED]) + 1)
    return spent


def _resource_of(headers: Mapping[str, str]) -> str:
    """The rate-limit resource an answer reports its quota for."""
    return headers.get(_QUOTA_RESOURCE, "core")


def _names_the_etag_of(request: httpx2.Request, answer: httpx2.Response) -> bool:
    """Whether `request` is conditional on the ETag `answer` carries."""
    etag = answer.headers.get("etag")
    return etag is not None and request.headers.get("if-none-match") == etag


def _not_modified(answer: httpx2.Response, quota: Mapping[str, str]) -> httpx2.Response:
    """GitHub's 304 in place of `answer`: its headers without its body, and without the `Link`
    header, which GitHub's 304 does not carry, reporting `quota`, the quota as it stands."""
    dropped = {"link", "content-type", "content-length"}
    headers = {name: value for name, value in answer.headers.items() if name not in dropped}
    return httpx2.Response(HTTPStatus.NOT_MODIFIED, headers={**headers, **quota})


class RecordedGitHubApi(GitHubApiDouble):
    """GitHub's REST API as recorded: each request gets the next answer GitHub gave, once the
    request is shown to be the one GitHub answered (#983).

    An exchange is a mapping of `request` (its `method`, its `url`, under `headers` the
    `If-None-Match` it was sent with, if any, and its JSON `body`, if any) and `response` (its
    `status`, `headers` as name and value pairs, and `body` as text). A request is matched on
    those four alone: one whose method, URL, `If-None-Match` or body differs from the next one
    recorded, or one sent after the last, fails the test, since GitHub's answer to it is unknown.
    A recorded `x-ratelimit-reset` is replayed as far ahead of now as it was ahead of the
    answer's `Date`, so a quota the recording reports never reads as past its reset.
    """

    def __init__(self, exchanges: Iterable[Mapping[str, Any]]) -> None:
        super().__init__()
        self._exchanges = list(exchanges)

    @property
    def unanswered(self) -> list[str]:
        """The method and URL of each recorded request no request has been answered with yet."""
        return [f"{e['request']['method']} {e['request']['url']}" for e in self._exchanges]

    def _answer(self, request: httpx2.Request) -> httpx2.Response:
        if not self._exchanges:
            raise AssertionError(
                f"GitHub was recorded answering no request after the last, but the session sent "
                f"{request.method} {request.url}"
            )
        exchange = self._exchanges.pop(0)
        recorded = exchange["request"]
        assert _as_recorded(request, recorded) == recorded, "the request GitHub answered differs"
        return _replayed(exchange["response"])


def _as_recorded(request: httpx2.Request, recorded: Mapping[str, Any]) -> dict[str, Any]:
    """`request` in the shape `recorded` has: its method, its URL, its `If-None-Match` if it
    sent one, and its JSON body where `recorded` holds one."""
    condition = request.headers.get("if-none-match")
    shown: dict[str, Any] = {
        "method": request.method,
        "url": str(request.url),
        "headers": {} if condition is None else {"if-none-match": condition},
    }
    if "body" in recorded:
        shown["body"] = json.loads(request.content)
    return shown


def _replayed(response: Mapping[str, Any]) -> httpx2.Response:
    """A recorded answer, its quota's reset moved to as far ahead of now as it was recorded."""
    headers = [(name, value) for name, value in response["headers"]]
    named = dict(headers)
    if "x-ratelimit-reset" in named and "date" in named:
        ahead = int(named["x-ratelimit-reset"]) - parsedate_to_datetime(named["date"]).timestamp()
        reset = str(int(time.time() + ahead))
        headers = [(n, reset if n == "x-ratelimit-reset" else v) for n, v in headers]
    return httpx2.Response(
        response["status"], headers=headers, content=response["body"].encode("utf-8")
    )


def serve_github_api(monkeypatch: pytest.MonkeyPatch, api: GitHubApiDouble) -> None:
    """Make `api` answer every GitHub session the test opens, as the `github_api` fixture does.

    The pinned identity's `core` quota is fresh, so pacing never runs `gh api rate_limit`; a
    quota that is unknown or past its reset fails the test instead of refreshing through gh.
    Any other gh child process the rate limiter would start fails the test too, offline, as
    when a reader falls back to `run_gh` instead of the session: a real gh would send the pinned
    fake token to GitHub. Neither the rate limiter's pauses nor the retry waits take any time:
    `api` records them in `paced` and `waits`, and only the rate limiter's clock and gidgethub's
    wait are replaced, so no other sleep changes.
    """
    from devops_cli.github import rate_limiter, session_transport

    def refuse_quota_refresh(_limiter: object) -> NoReturn:
        raise AssertionError(
            "A test over the fake GitHub API reached `gh api rate_limit`: give the resource a "
            "quota whose reset is still ahead, built when the test runs."
        )

    def refuse_gh(argv: list[str], *_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError(f"A test over the fake GitHub API ran gh: {argv[:4]}")

    install_async_client_fake(monkeypatch, api.client_class())
    monkeypatch.setattr(
        rate_limiter.GitHubRateLimiter, "_refresh_from_github", refuse_quota_refresh
    )
    monkeypatch.setattr(rate_limiter, "run_subprocess", refuse_gh)
    monkeypatch.setattr(rate_limiter, "time", PacedClock(api.paced))
    monkeypatch.setattr(session_transport.SessionGitHubAPI, "sleep", api.wait)
    rate_limiter.get_github_rate_limiter().update_quota(
        "core", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )


@pytest.fixture
def github_api(
    monkeypatch: pytest.MonkeyPatch, pin_github_session: str, public_dns: str
) -> GitHubApiFake:
    """GitHub's API, faked for every GitHub session the test opens.

    The session's client is still built by the egress factory; as with `stub_web`, only its
    transport is the fake's, so every request goes through the session's redirect handling and
    origin hook, and its host is vetted at the factory's egress level, resolving as `public_dns`
    resolves it. A test cannot ask for this fixture and `stub_web` together. What else it
    replaces is `serve_github_api`'s.
    """
    api = GitHubApiFake()
    serve_github_api(monkeypatch, api)
    return api


class RunnerSession:
    """A GitHub session whose REST listings a scripted gh runner answers, for the roadmap store
    tests that script gh for the board as well (#983).

    `paginate` asks the runner with the listing's URL as its one argument, so a reply keyed by
    the listing's path answers it, the runner records the read beside the gh commands, and a
    read the store sends through gh instead is told apart. A reply holding a list is the whole
    listing; a failed one raises the class the gh classifier makes of its stderr, else the
    unread error; anything else fails closed through the session's own `listed_items`. Paging,
    a failed page, the page cap and the class each HTTP failure raises are the real session's,
    and are tested only over `GitHubApiFake`.
    """

    def __init__(self, runner: Callable[..., subprocess.CompletedProcess[str]]) -> None:
        self._runner = runner

    def paginate(self, path: str, *, iterable_key: str | None = None) -> Iterator[Any]:
        from devops_cli.exceptions.git import GitHubUnreadError
        from devops_cli.github.error_classifier import classify_gh_failure
        from devops_cli.github.session_transport import listed_items

        reply = self._runner([f"{API}{path}"], check=False, quiet=True, use_cache=False)
        if reply.returncode != 0:
            said = (reply.stderr or reply.stdout or "").strip()[:256]
            raise classify_gh_failure(
                reply.stderr or "", exit_code=reply.returncode
            ) or GitHubUnreadError(
                f"GitHub gave no readable answer to GET {path}: {said}", details={"path": path}
            )
        try:
            answer = json.loads(reply.stdout or "null")
        except json.JSONDecodeError as exc:
            raise GitHubUnreadError(
                f"GitHub's answer to GET {path} is no JSON", details={"path": path}
            ) from exc
        yield from listed_items(answer, path=path, page=1, iterable_key=iterable_key)
