"""A fake GitHub REST API at the HTTP edge, for tests of the GitHub session (#983).

`GitHubApiFake` answers the session's requests through httpx2's own `MockTransport`, reached the
way `stub_web` reaches canned pages: `client_class()` is an `httpx2.AsyncClient` that keeps
everything the factory gave it except the transport. The factory, its timeouts and the session's
options stay real, so the session's client follows redirects and runs its origin hook exactly as
it does against GitHub, gidgethub decodes each answer as it decodes GitHub's, and every request's
host is still vetted at the egress level the factory built the client for. The `github_api`
fixture in `tests/conftest.py` installs it for the process's session.

A route answers with its responses in order, and its last response repeats. A response may be an
`httpx2.TransportError` class, which is raised for the request instead, as a refused connect is.
A request whose `If-None-Match` names the ETag of the response it would get gets a 304 instead,
with that response's headers but no body and no `Link`, as GitHub answers one (checked against
GitHub on 2026-10-19). A request no route names gets GitHub's 404. With `delay` set, each answer arrives that many
seconds after its request, so requests can be in flight together. The fake records every request
it receives, each client it answers and that client's egress level, the pauses the rate limiter
asked for and the waits gidgethub's retry hook asked for; neither takes any time.

`RunnerSession` is a session whose listings a scripted gh runner answers, for the roadmap store
tests that script gh for the board as well.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Awaitable, Callable, Iterator
from typing import Any

import anyio
import httpx2

from devops_cli.http.egress import EgressLevel
from tests.web_fakes import egress_level_of, vetted_handler

API = "https://api.github.com"
JSON_TYPE = "application/json; charset=utf-8"
# What a fake client says faked httpx2.AsyncClient, so a second fake in one test is refused.
FAKE_OWNER_ATTRIBUTE = "fake_owner"

Answer = httpx2.Response | type[httpx2.TransportError]


def github_json(
    payload: Any = None, *, status: int = 200, headers: dict[str, str] | None = None
) -> httpx2.Response:
    """A response with a JSON body, as GitHub's REST API answers."""
    body = b"" if payload is None else json.dumps(payload).encode()
    return httpx2.Response(
        status, headers={"content-type": JSON_TYPE, **(headers or {})}, content=body
    )


def github_text(text: str, *, media_type: str, status: int = 200) -> httpx2.Response:
    """A response whose body is `text` of `media_type`, as a diff is served."""
    return httpx2.Response(
        status, headers={"content-type": f"{media_type}; charset=utf-8"}, content=text.encode()
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


class PacedClock:
    """The `time` module as the rate limiter reads it, except that a pause is recorded in `paced`
    instead of slept, so a test paces without waiting and nothing else's sleep changes."""

    def __init__(self, paced: list[float]) -> None:
        self.sleep = paced.append

    def __getattr__(self, name: str) -> Any:
        return getattr(time, name)


class GitHubApiFake:
    """GitHub's REST API, answered from routes, recording every request it receives."""

    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], list[Answer]] = {}
        self.sent: list[httpx2.Request] = []
        self.levels: list[EgressLevel | None] = []
        self.clients: list[httpx2.AsyncClient] = []
        self.paced: list[float] = []
        self.waits: list[float] = []
        self.delay = 0.0

    @property
    def requested(self) -> list[str]:
        """Each request's method and URL, in the order the fake received them."""
        return [f"{request.method} {request.url}" for request in self.sent]

    def client_class(self) -> type[httpx2.AsyncClient]:
        """An `httpx2.AsyncClient` that answers from this fake in place of the transport it was
        given, after vetting each request at that transport's egress level."""
        fake = self

        class GitHubApiClient(httpx2.AsyncClient):
            fake_owner = "github_api"

            def __init__(self, **kwargs: Any) -> None:
                level = egress_level_of(kwargs.get("transport"))
                fake.levels.append(level)
                transport = httpx2.MockTransport(vetted_handler(fake._handle, level))
                super().__init__(**{**kwargs, "transport": transport})
                fake.clients.append(self)

        return GitHubApiClient

    def route(self, method: str, url: str, *answers: Answer) -> None:
        """Answer `method` on `url` (absolute, or a path under the API) with `answers` in turn."""
        self._routes[(method, str(httpx2.URL(API).join(url)))] = list(answers)

    async def wait(self, seconds: float) -> None:
        """Stand in for gidgethub's `sleep`: record the retry wait and return at once."""
        self.waits.append(seconds)

    def _handle(self, request: httpx2.Request) -> httpx2.Response | Awaitable[httpx2.Response]:
        """Record `request` and give it its route's next answer, `delay` seconds later."""
        self.sent.append(request)
        response = self._answer(request)
        return self._later(response) if self.delay else response

    def _answer(self, request: httpx2.Request) -> httpx2.Response:
        answers = self._routes.get((request.method, str(request.url)))
        if not answers:
            return github_json({"message": "Not Found"}, status=404)
        answer = answers.pop(0) if len(answers) > 1 else answers[0]
        if isinstance(answer, type):
            raise answer("connection refused", request=request)
        if _names_the_etag_of(request, answer):
            return _not_modified(answer)
        return httpx2.Response(answer.status_code, headers=answer.headers, content=answer.content)

    async def _later(self, response: httpx2.Response) -> httpx2.Response:
        await anyio.sleep(self.delay)
        return response


def _names_the_etag_of(request: httpx2.Request, answer: httpx2.Response) -> bool:
    """Whether `request` is conditional on the ETag `answer` carries."""
    etag = answer.headers.get("etag")
    return etag is not None and request.headers.get("if-none-match") == etag


def _not_modified(answer: httpx2.Response) -> httpx2.Response:
    """GitHub's 304 in place of `answer`: its headers without its body, and without the `Link`
    header, which GitHub's 304 does not carry."""
    dropped = {"link", "content-type", "content-length"}
    headers = {name: value for name, value in answer.headers.items() if name not in dropped}
    return httpx2.Response(304, headers=headers)


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
