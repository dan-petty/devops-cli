"""Canned web pages and connects for tests that fetch over HTTP and must not reach the network.

`StubWeb` answers pages through httpx2's own `MockTransport`, so a client under test follows
redirects and runs its request hooks exactly as it would against a real server. `ConnectRecorder`
and `ScriptedResolver` sit one layer lower, at the socket: they stand in for httpcore2's dial and
for `socket.getaddrinfo`, so a test sees which address a client dialled after which lookups.
Hosts are `example.com`, as AGENTS.md requires of fixtures, and `example.org` where a second
hostname is the point of the test.
"""

from __future__ import annotations

import socket
import ssl
from collections.abc import Callable, Iterable, Sequence
from http import HTTPStatus
from typing import Any

import h11
import httpcore2
import httpx2

from devops_cli.http.egress import AsyncVettingBackend, EgressLevel, VettingBackend, vet_addresses

PUBLIC_ADDRESS = "93.184.215.14"


def http_response(status: int, body: str = "", headers: dict[str, str] | None = None) -> bytes:
    """One HTTP/1.1 response to a GET, as h11 serialises it for a server to write to the socket."""
    payload = body.encode()
    server = h11.Connection(h11.SERVER)
    request = h11.Request(method="GET", target="/", headers=[("Host", "example.com")])
    server.receive_data(h11.Connection(h11.CLIENT).send(request) or b"")
    server.next_event()
    fields = [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(payload))),
        *(headers or {}).items(),
    ]
    events = (
        h11.Response(status_code=status, reason=HTTPStatus(status).phrase, headers=fields),
        h11.Data(data=payload),
        h11.EndOfMessage(),
    )
    return b"".join(server.send(event) or b"" for event in events)


class ConnectRecorder:
    """Stands in for httpcore2's dial: records each connect and answers it with the next response.

    Patched over `httpcore2.SyncBackend.connect_tcp` (and `AnyIOBackend.connect_tcp` through
    `aconnect_tcp`), it receives what the vetting backend dials, so `dialled` shows whether a
    hostname or an unvetted address ever reached the socket, and `timeouts_of` the bound each dial
    was given. `written` holds the bytes written on each connection, in dial order.
    """

    def __init__(self, *responses: bytes) -> None:
        self.responses = list(responses)
        self.dialled: list[tuple[str, int]] = []
        self._timeouts: list[float | None] = []
        self.tls: list[tuple[str | None, ssl.SSLContext]] = []
        self.written: list[bytearray] = []

    def _dial(self, host: str, port: int, timeout: float | None) -> tuple[list[bytes], bytearray]:
        """Record one dial; return its canned response and the buffer its writes go to."""
        self.dialled.append((host, port))
        self._timeouts.append(timeout)
        self.written.append(bytearray())
        return ([self.responses.pop(0)] if self.responses else []), self.written[-1]

    def connect_tcp(
        self, host: str, port: int, timeout: float | None = None, *args: Any, **kwargs: Any
    ) -> RecordingStream:
        """Record the dial and return a stream holding the next canned response."""
        return RecordingStream(self, *self._dial(host, port, timeout))

    async def aconnect_tcp(
        self, host: str, port: int, timeout: float | None = None, *args: Any, **kwargs: Any
    ) -> AsyncRecordingStream:
        """`connect_tcp` for httpcore2's async backends."""
        return AsyncRecordingStream(self, *self._dial(host, port, timeout))

    def timeouts_of(self, address: str) -> list[float | None]:
        """The connect timeout of each dial to `address`, in order.

        Selecting by address leaves out the test configuration's telemetry exporter, which may dial
        its collector from a background thread during a test.
        """
        dials = zip(self.dialled, self._timeouts, strict=True)
        return [timeout for (host, _), timeout in dials if host == address]

    @property
    def requested_hosts(self) -> list[str]:
        """The Host header of the request written on each recorded connection, as h11 parses it."""
        hosts: list[str] = []
        for written in self.written:
            server = h11.Connection(h11.SERVER)
            server.receive_data(bytes(written))
            if isinstance(request := server.next_event(), h11.Request):
                hosts.append(dict(request.headers)[b"host"].decode())
        return hosts


class RecordingStream(httpcore2.MockStream):
    """httpcore2's mock stream, recording the TLS handshake and the request bytes."""

    def __init__(self, recorder: ConnectRecorder, buffer: list[bytes], written: bytearray) -> None:
        super().__init__(buffer)
        self.recorder = recorder
        self.written = written

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self.written.extend(buffer)

    def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore2.NetworkStream:
        self.recorder.tls.append((server_hostname, ssl_context))
        return self


class AsyncRecordingStream(httpcore2.AsyncMockStream):
    """The async `RecordingStream`."""

    def __init__(self, recorder: ConnectRecorder, buffer: list[bytes], written: bytearray) -> None:
        super().__init__(buffer)
        self.recorder = recorder
        self.written = written

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self.written.extend(buffer)

    async def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore2.AsyncNetworkStream:
        self.recorder.tls.append((server_hostname, ssl_context))
        return self


def _answer(address: str, port: Any) -> tuple[Any, ...]:
    """One `getaddrinfo` answer for `address`."""
    number = int(port) if isinstance(port, int) or str(port or "").isdigit() else 0
    if ":" in address:
        return (
            socket.AF_INET6,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (address, number, 0, 0),
        )
    return (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, number))


class ScriptedResolver:
    """A stub `socket.getaddrinfo` whose answers for a name can change between lookups.

    `script[name]` lists, per lookup, the addresses that lookup answers; the last entry repeats.
    Every other host goes to `fallback`, the session's guarded resolver, so numeric hosts and
    loopback still resolve as they do in production. `lookups` counts the lookups of each name.
    """

    def __init__(
        self, script: dict[str, Sequence[Sequence[str]]], fallback: Callable[..., Any]
    ) -> None:
        self.script = script
        self.fallback = fallback
        self.lookups: dict[str, int] = dict.fromkeys(script, 0)

    def __call__(self, host: Any, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        name = host.decode() if isinstance(host, bytes) else str(host)
        if name not in self.script:
            return list(self.fallback(host, port, *args, **kwargs))
        answers = self.script[name]
        index = min(self.lookups[name], len(answers) - 1)
        self.lookups[name] += 1
        return [_answer(address, port) for address in answers[index]]


def rebinding(k: int, then: str) -> list[list[str]]:
    """A name's lookups: the public address for the first `k`, then `then` for every later one."""
    return [*([[PUBLIC_ADDRESS]] * k), [then]]


def scripted_resolver(
    monkeypatch: Any, script: dict[str, Sequence[Sequence[str]]]
) -> ScriptedResolver:
    """Install a `ScriptedResolver` over `socket.getaddrinfo` for the rest of the test."""
    resolver = ScriptedResolver(script, socket.getaddrinfo)
    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    return resolver


def record_connects(monkeypatch: Any, responses: Iterable[bytes]) -> ConnectRecorder:
    """Patch httpcore2's sync and async dials with a `ConnectRecorder` serving `responses`."""
    recorder = ConnectRecorder(*responses)
    monkeypatch.setattr(httpcore2.SyncBackend, "connect_tcp", recorder.connect_tcp)
    monkeypatch.setattr(httpcore2.AnyIOBackend, "connect_tcp", recorder.aconnect_tcp)
    return recorder


def egress_level_of(transport: Any) -> EgressLevel | None:
    """The egress level of a factory-built transport, through any retry wrappers, or None."""
    while transport is not None:
        backend = getattr(getattr(transport, "_pool", None), "_network_backend", None)
        if isinstance(backend, (VettingBackend, AsyncVettingBackend)):
            return backend.level
        transport = getattr(transport, "wrapped", None)
    return None


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

    def vetting_handler(
        self, level: EgressLevel | None
    ) -> Callable[[httpx2.Request], httpx2.Response]:
        """`handle`, after vetting the request's host at `level` as the connect would."""
        if level is None:
            return self.handle

        def handle_vetted(request: httpx2.Request) -> httpx2.Response:
            vet_addresses(request.url.host, request.url.port or 0, level)
            return self.handle(request)

        return handle_vetted
