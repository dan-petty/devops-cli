"""Canned web pages for tests that fetch over HTTP and must not reach the network.

Pages are answered by httpx2's own `MockTransport`, so a client under test follows redirects and
runs its request hooks exactly as it would against a real server. Hosts are `example.com`, as
AGENTS.md requires of fixtures.
"""

from __future__ import annotations

import httpx2


class StubWeb:
    """Canned pages answered by httpx2's MockTransport, recording every request it receives."""

    def __init__(self) -> None:
        self.routes: dict[str, tuple[int, dict[str, str], str]] = {}
        self.sent: list[httpx2.Request] = []

    @property
    def requested(self) -> list[str]:
        """Return the URL of each request the transport received, in order."""
        return [str(request.url) for request in self.sent]

    def page(self, url: str, html: str, headers: dict[str, str] | None = None) -> None:
        """Serve `html` at `url`, with any extra response `headers`."""
        self.routes[url] = (
            200,
            {"content-type": "text/html; charset=utf-8", **(headers or {})},
            html,
        )

    def redirect(self, url: str, location: str, status: int = 302) -> None:
        """Answer `url` with a redirect to `location`; a 307 or 308 keeps the method and body."""
        self.routes[url] = (status, {"location": location}, "")

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        """Record `request` and answer it from the routes, or with a 404."""
        self.sent.append(request)
        status, headers, body = self.routes.get(str(request.url), (404, {}, ""))
        return httpx2.Response(status, headers=headers, content=body.encode())
