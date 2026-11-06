"""The dial of httpcore2 faked for tests: which address a client connects to, with no socket (#1314).

`ConnectRecorder` stands in for httpcore2's dial. Patched over `httpcore2.SyncBackend.connect_tcp`
(and `AnyIOBackend.connect_tcp` through `aconnect_tcp`) by `record_connects`, it receives what the
vetting backend of `devops_cli.http.egress` dials. A test sees which address a client dialled, after
which lookups of the `dns` fixture, the TLS handshake it asked for, the bytes it wrote and the
bound of each dial. `http_response` gives the bytes of one response for a connection to serve.

This is the seam below the pool. A test of the egress policy needs it, because the policy runs at
the connect. A test of a caller needs the `web` fake (`tests/support/fakes/http.py`), which sits
above the pool at httpx2's transport interface.
Hosts are `example.com`, as docs/TESTING.md requires of fixtures, and `example.org` where a second
hostname is the point of the test.
"""

from __future__ import annotations

import ssl
from collections.abc import Iterable
from http import HTTPStatus
from typing import Any

import h11
import httpcore2
import pytest


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


def record_connects(monkeypatch: pytest.MonkeyPatch, responses: Iterable[bytes]) -> ConnectRecorder:
    """Patch httpcore2's sync and async dials with a `ConnectRecorder` serving `responses`."""
    recorder = ConnectRecorder(*responses)
    monkeypatch.setattr(httpcore2.SyncBackend, "connect_tcp", recorder.connect_tcp)
    monkeypatch.setattr(httpcore2.AnyIOBackend, "connect_tcp", recorder.aconnect_tcp)
    return recorder
