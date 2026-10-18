"""A fake GitHub REST API at the HTTP edge, for tests of the GitHub session (#983).

`GitHubApiFake` answers the session's requests through httpx2's own `MockTransport`, so the
session's client follows redirects and runs its origin hook exactly as it does against GitHub, and
gidgethub decodes each answer as it decodes GitHub's. The `github_api` fixture in
`tests/conftest.py` builds the process's session over it.

A route answers with its responses in order, and its last response repeats. A response may be an
`httpx2.TransportError` class, which is raised for the request instead, as a refused connect is.
A request no route names gets GitHub's 404. The fake records every request it receives, the
pauses the rate limiter asked for and the waits gidgethub's retry hook asked for; neither takes
any time.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx2

API = "https://api.github.com"
JSON_TYPE = "application/json; charset=utf-8"

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
        self.paced: list[float] = []
        self.waits: list[float] = []

    @property
    def transport(self) -> httpx2.MockTransport:
        """The transport the session's client sends through."""
        return httpx2.MockTransport(self._handle)

    @property
    def requested(self) -> list[str]:
        """Each request's method and URL, in the order the fake received them."""
        return [f"{request.method} {request.url}" for request in self.sent]

    def route(self, method: str, url: str, *answers: Answer) -> None:
        """Answer `method` on `url` (absolute, or a path under the API) with `answers` in turn."""
        self._routes[(method, str(httpx2.URL(API).join(url)))] = list(answers)

    async def wait(self, seconds: float) -> None:
        """Stand in for gidgethub's `sleep`: record the retry wait and return at once."""
        self.waits.append(seconds)

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        """Record `request` and give it its route's next answer."""
        self.sent.append(request)
        answers = self._routes.get((request.method, str(request.url)))
        if not answers:
            return github_json({"message": "Not Found"}, status=404)
        answer = answers.pop(0) if len(answers) > 1 else answers[0]
        if isinstance(answer, type):
            raise answer("connection refused", request=request)
        return httpx2.Response(answer.status_code, headers=answer.headers, content=answer.content)
