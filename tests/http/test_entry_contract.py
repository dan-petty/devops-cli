"""Contract suite for the HTTP seam (`devops_cli.http.entry`), `WebFake` and the real transport (#1314).

Each case runs a client that the entry point builds against two peers: `WebFake`, which the `web`
fixture installs through the transport hook, and a loopback server the test owns, which the client
reaches over the real egress transport. Both peers must give the same status, headers and body,
follow redirects by httpx2's rules, raise the same httpx2 errors, and refuse a destination that
SSRF validation refuses before any request is sent. Every case finishes well under 1 s.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx2
import pytest

from devops_cli.config.defaults import DEFAULT_HTTP_MAX_REDIRECTS
from devops_cli.exceptions import SSRFBlockedError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import async_http_client, http_client
from tests.support.fakes.http import WebFake

_READ_TIMEOUT_SECONDS = 0.2
_HOLD_SECONDS = 2.0
_FAKE_BASE = "http://127.0.0.1:8200"


class _Handler(BaseHTTPRequestHandler):
    """The loopback server's one handler: it answers from the routes and records each request."""

    server: _Server

    def do_GET(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self.server.received.append((self.command, self.path, body))
        if self.path in self.server.held:
            self.server.release.wait(_HOLD_SECONDS)
            return
        status, headers, content = self.server.routes.get(self.path, (404, {}, b""))
        self.send_response(status)
        for name, value in {**headers, "Content-Length": str(len(content))}.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        self.do_GET()

    def log_message(self, format: str, *args: Any) -> None:
        """Keep the server quiet."""


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.routes: dict[str, tuple[int, dict[str, str], bytes]] = {}
        self.held: set[str] = set()
        self.received: list[tuple[str, str, bytes]] = []
        self.release = threading.Event()


@dataclass
class Peer:
    """One side of the contract: where it listens, how it answers and what it received."""

    base: str
    route: Callable[[str, int, dict[str, str], bytes], None]
    redirect: Callable[[str, str], None]
    hold: Callable[[str], None]
    received: Callable[[], list[tuple[str, str, bytes]]]
    refused: str

    def url(self, path: str) -> str:
        return f"{self.base}{path}"


def _fake_peer(web: WebFake, refusing_port: int) -> Peer:
    refused = f"http://127.0.0.1:{refusing_port}/"
    web.refuse(refused)

    def received() -> list[tuple[str, str, bytes]]:
        return [
            (r.method, httpx2.URL(r.url).raw_path.decode(), r.body)
            for r in web.recorded
            if r.url != refused
        ]

    return Peer(
        base=_FAKE_BASE,
        route=lambda path, status, headers, body: web.answer(
            f"{_FAKE_BASE}{path}", status, headers=headers, body=body
        ),
        redirect=lambda path, location: web.redirect(
            f"{_FAKE_BASE}{path}", f"{_FAKE_BASE}{location}"
        ),
        hold=lambda path: web.time_out(f"{_FAKE_BASE}{path}"),
        received=received,
        refused=refused,
    )


def _real_peer(server: _Server, refusing_port: int) -> Peer:
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def route(path: str, status: int, headers: dict[str, str], body: bytes) -> None:
        server.routes[path] = (status, headers, body)

    return Peer(
        base=base,
        route=route,
        redirect=lambda path, location: server.routes.__setitem__(
            path, (302, {"Location": f"{base}{location}"}, b"")
        ),
        hold=server.held.add,
        received=lambda: list(server.received),
        refused=f"http://127.0.0.1:{refusing_port}/",
    )


@pytest.fixture
def server() -> Iterator[_Server]:
    """The loopback server that the real side of the contract talks to."""
    running = _Server()
    # A short poll, so `shutdown` returns at once at teardown.
    thread = threading.Thread(target=running.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    try:
        yield running
    finally:
        running.release.set()
        running.shutdown()
        running.server_close()
        thread.join()


@pytest.fixture(params=["fake", "real"])
def peer(request: pytest.FixtureRequest) -> Peer:
    """The peer a client talks to: the fake behind the hook, or the loopback server."""
    refusing_port: int = request.getfixturevalue("refusing_port")
    if request.param == "fake":
        return _fake_peer(request.getfixturevalue("web"), refusing_port)
    return _real_peer(request.getfixturevalue("server"), refusing_port)


def _send(
    kind: str,
    method: str,
    url: str,
    *,
    level: EgressLevel = EgressLevel.LOOPBACK,
    **options: Any,
) -> httpx2.Response:
    """Send one request with a client from the entry point, sync or async, and close the client."""
    client_options: dict[str, Any] = {"read_timeout": _READ_TIMEOUT_SECONDS}
    if "max_redirects" in options:
        client_options["max_redirects"] = options.pop("max_redirects")
    if kind == "sync":
        with http_client(level, follow_redirects=True, **client_options) as client:
            return client.request(method, url, **options)

    async def send() -> httpx2.Response:
        async with async_http_client(level, follow_redirects=True, **client_options) as client:
            return await client.request(method, url, **options)

    return asyncio.run(send())


kinds = pytest.mark.parametrize("kind", ["sync", "async"])


@kinds
def test_status_headers_and_body_round_trip(peer: Peer, kind: str) -> None:
    """The client gets the status, a header and the body that the peer sent."""
    peer.route("/page", 201, {"X-Reply": "yes", "Content-Type": "text/plain"}, b"hello")

    response = _send(kind, "GET", peer.url("/page"))

    assert (
        response.status_code,
        response.headers["x-reply"],
        response.content,
        peer.received(),
    ) == (201, "yes", b"hello", [("GET", "/page", b"")])


@kinds
def test_a_json_request_reaches_the_peer_and_a_json_answer_comes_back(
    peer: Peer, kind: str
) -> None:
    """A JSON body is sent as JSON, and a JSON answer decodes."""
    peer.route("/items", 200, {"Content-Type": "application/json"}, b'{"id": 7}')

    response = _send(kind, "POST", peer.url("/items"), json={"name": "box"})

    assert (response.json(), peer.received()) == (
        {"id": 7},
        [("POST", "/items", b'{"name":"box"}')],
    )


@kinds
def test_a_redirect_is_followed_to_its_target(peer: Peer, kind: str) -> None:
    """The client follows a 302 and asks the target, so the peer sees both requests."""
    peer.redirect("/start", "/final")
    peer.route("/final", 200, {}, b"arrived")

    response = _send(kind, "GET", peer.url("/start"))

    assert (response.content, [path for _, path, _ in peer.received()]) == (
        b"arrived",
        ["/start", "/final"],
    )


@kinds
def test_a_redirect_loop_stops_at_the_redirect_limit(peer: Peer, kind: str) -> None:
    """A loop raises TooManyRedirects after the limit, with one request more than the limit."""
    peer.redirect("/loop", "/loop")

    with pytest.raises(httpx2.TooManyRedirects) as raised:
        _send(kind, "GET", peer.url("/loop"), max_redirects=DEFAULT_HTTP_MAX_REDIRECTS)

    assert (raised.value.request.url.path, len(peer.received())) == (
        "/loop",
        DEFAULT_HTTP_MAX_REDIRECTS + 1,
    )


@kinds
def test_a_refused_connection_is_an_httpx2_connect_error(peer: Peer, kind: str) -> None:
    """A port with nothing listening raises httpx2.ConnectError."""
    with pytest.raises(httpx2.ConnectError) as raised:
        _send(kind, "GET", peer.refused)
    assert str(raised.value.request.url) == peer.refused


@kinds
def test_a_response_that_does_not_come_is_an_httpx2_read_timeout(peer: Peer, kind: str) -> None:
    """A peer that takes the request and does not answer in time raises httpx2.ReadTimeout."""
    peer.hold("/slow")

    with pytest.raises(httpx2.ReadTimeout) as raised:
        _send(kind, "GET", peer.url("/slow"))

    assert (raised.value.request.url.path, [path for _, path, _ in peer.received()]) == (
        "/slow",
        ["/slow"],
    )


@kinds
def test_a_destination_that_ssrf_validation_refuses_is_refused_before_any_request(
    peer: Peer, kind: str
) -> None:
    """The public level refuses loopback, and the peer never sees the request."""
    peer.route("/secret", 200, {}, b"private")

    with pytest.raises(SSRFBlockedError) as raised:
        _send(kind, "GET", peer.url("/secret"), level=EgressLevel.PUBLIC)

    assert (raised.value.error_code, peer.received()) == ("SSRF_BLOCKED", [])
