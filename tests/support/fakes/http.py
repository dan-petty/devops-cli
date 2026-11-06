"""The HTTP seam faked for tests: canned answers over httpx2's own `MockTransport` (#1314).

`WebFake` is the transport that every client built by `devops_cli.http.entry` takes while the `web`
fixture is active. A client under test follows redirects and runs its request hooks exactly as it
does against a real server, because the fake sits below the client, at httpx2's transport interface.
The fake vets each request's host at the client's egress level with `vet_addresses`, as the real
transport vets what it dials, so a destination that SSRF validation refuses fails before any request
is recorded. A name that is not an IP literal needs a DNS answer, from the `dns` fixture (`DnsFake`).

Its answers go by method and URL. `recorded` holds each request that reached the fake as one value
(method, URL, headers and body), so a test compares the requests as a list. `refuse` and `time_out`
raise httpx2's connect and read-timeout errors, the ones the real transport raises.
`tests/http/test_entry_contract.py` holds the fake to the real transport.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import httpx2
import pytest

from devops_cli.http.egress import EgressLevel, vet_addresses
from devops_cli.http.entry import install_transport, remove_transport
from tests.support.fakes.dns import DnsFake


@dataclass(frozen=True)
class RecordedRequest:
    """One request that reached the fake, as plain values a test can compare."""

    method: str
    url: str
    headers: dict[str, str]
    body: bytes

    @property
    def json(self) -> Any:
        """The body decoded as JSON."""
        return json.loads(self.body)


class WebFake:
    """Canned answers by method and URL, over httpx2's `MockTransport`, recording every request."""

    def __init__(self) -> None:
        self.routes: dict[str, tuple[int, dict[str, str], bytes]] = {}
        self.servers: list[Callable[[httpx2.Request], httpx2.Response | None]] = []
        self.method_routes: dict[tuple[str, str], tuple[int, dict[str, str], bytes]] = {}
        self.failures: dict[str, httpx2.TransportError] = {}
        self.sent: list[httpx2.Request] = []
        self.recorded: list[RecordedRequest] = []

    @property
    def requested(self) -> list[str]:
        """Return the URL of each request the transport received, in order."""
        return [str(request.url) for request in self.sent]

    def page(self, url: str, html: str, headers: dict[str, str] | None = None) -> None:
        """Serve `html` at `url`, with any extra response `headers`."""
        self.routes[url] = (
            200,
            {"content-type": "text/html; charset=utf-8", **(headers or {})},
            html.encode(),
        )

    def content(self, url: str, body: bytes) -> None:
        """Serve the raw `body` bytes at `url`, as a release asset or an archive is served."""
        self.routes[url] = (200, {"content-type": "application/octet-stream"}, body)

    def redirect(self, url: str, location: str, status: int = 302) -> None:
        """Answer `url` with a redirect to `location`; a 307 or 308 keeps the method and body."""
        self.routes[url] = (status, {"location": location}, b"")

    def answer(
        self,
        url: str,
        status: int,
        *,
        method: str | None = None,
        headers: dict[str, str] | None = None,
        body: bytes | str = b"",
    ) -> None:
        """Answer requests to `url` with `status`, `headers` and `body`.

        With a `method` only that method gets the answer, and it comes before any answer for the
        URL alone, so one URL can list on GET and create on POST, as a REST collection does.
        """
        content = body.encode() if isinstance(body, str) else body
        route = (status, dict(headers or {}), content)
        if method is None:
            self.routes[url] = route
        else:
            self.method_routes[(method, url)] = route

    def serve(self, server: Callable[[httpx2.Request], httpx2.Response | None]) -> None:
        """Answer each request that `server` answers before the routes. A server gives None for
        a request it does not serve. It stands in for a service whose answer depends on the
        method or the body, such as an API that makes a resource under a name in the body."""
        self.servers.append(server)

    def respond(self, method: str, url: str, status: int, body: object = None) -> None:
        """Answer `method` requests to `url` with `status` and `body` as JSON.

        A route for a method comes before the page of its URL, so one URL can list on GET and
        create on POST, as a REST collection does. A `body` of None sends no content.
        """
        content = b"" if body is None else json.dumps(body).encode()
        self.method_routes[(method, url)] = (status, {"content-type": "application/json"}, content)

    def fail(self, url: str, error: httpx2.TransportError) -> None:
        """Raise `error` for each request to `url`, as a client sees a timeout or a lost connection."""
        self.failures[url] = error

    def refuse(self, url: str) -> None:
        """Refuse each connection to `url`, as a host with nothing listening does."""
        self.fail(url, httpx2.ConnectError("Connection refused"))

    def time_out(self, url: str) -> None:
        """Let each request to `url` time out waiting for the response."""
        self.fail(url, httpx2.ReadTimeout("The read operation timed out"))

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        """Record `request` and answer it from the failures, the servers, then the routes, or with
        a 404."""
        self.sent.append(request)
        url = str(request.url)
        self.recorded.append(
            RecordedRequest(request.method, url, dict(request.headers), request.read())
        )
        if (error := self.failures.get(url)) is not None:
            error.request = request
            raise error
        for server in self.servers:
            if (response := server(request)) is not None:
                return response
        route = self.method_routes.get((request.method, url)) or self.routes.get(url)
        status, headers, body = route or (404, {}, b"")
        return httpx2.Response(status, headers=headers, content=body)

    def vetting_handler(
        self, level: EgressLevel | None
    ) -> Callable[[httpx2.Request], httpx2.Response]:
        """`handle`, after vetting the request's host at `level` as the connect would."""
        return vetted_handler(self.handle, level)

    def transport(self, level: EgressLevel) -> httpx2.MockTransport:
        """The transport for a client at `level`: what `install_transport` takes."""
        return httpx2.MockTransport(self.vetting_handler(level))


def vetted_handler[Answer](
    handler: Callable[[httpx2.Request], Answer], level: EgressLevel | None
) -> Callable[[httpx2.Request], Answer]:
    """`handler`, after vetting each request's host at `level` as the connect of a client of the entry point
    would; `handler` itself when `level` is None."""
    if level is None:
        return handler

    def handle_vetted(request: httpx2.Request) -> Answer:
        vet_addresses(request.url.host, request.url.port or 0, level)
        return handler(request)

    return handle_vetted


@pytest.fixture
def web(dns: DnsFake) -> Iterator[WebFake]:
    """Install `WebFake` as the transport of every client the HTTP entry point builds, and return it.

    The fixture removes it at teardown, after closing the pooled clients that used it.
    """
    dns.answer_every_name()
    fake = WebFake()
    install_transport(fake.transport)
    try:
        yield fake
    finally:
        remove_transport()
