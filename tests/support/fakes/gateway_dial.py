"""A gateway behind the dial of httpcore2, for embedding tests that need a reply to a socket (#2011).

`Gateway` is the gateway side of each connection that the HTTP client of an embeddings engine
dials. `dial_gateway` connects every dial of httpcore2 to one `Gateway`. The httpx2 client, its
egress check and the connection pool stay real, and only the socket under each connection is the
gateway's. The `web` fake sits above the pool and cannot show a reply that arrives after the client
closed its connection, or the read timeout of one request, which is what this fake is for.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from typing import Any

import h11
import httpcore2
import httpx2
import pytest

from tests.support.embedding_replies import GATEWAY_URL
from tests.support.fakes.dns import PUBLIC_ADDRESS, DnsFake
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

REPLY_WIDTH = 4


def request_texts(request: bytes) -> list[str]:
    """The texts of one `/v1/embeddings` request, as the HTTP/1.1 parser of a server reads them."""
    server = h11.Connection(h11.SERVER)
    server.receive_data(request)
    body = b""
    while not isinstance(event := server.next_event(), h11.EndOfMessage):
        if event is h11.NEED_DATA:
            pytest.fail("The engine read the reply before it wrote all of its request")
        if isinstance(event, h11.Data):
            body += event.data
    return list(json.loads(body)["input"])


def reply_bytes(texts: list[str], value: float = 0.5) -> bytes:
    """The HTTP/1.1 reply of a gateway to `texts`: one vector of `value` for each text."""
    body = json.dumps(
        {
            "data": [{"index": i, "embedding": [value] * REPLY_WIDTH} for i in range(len(texts))],
            "usage": {"prompt_tokens": len(texts), "total_tokens": len(texts)},
        }
    ).encode()
    head = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n"
    return f"{head}\r\n".encode() + body


class Gateway:
    """The gateway side of each connection that the HTTP client of the engine dials.

    `answer` gets the texts and the read timeout of one request. It gives the reply bytes, or it
    raises the timeout or network error that a socket read raises. `requests` holds the texts of
    each request and `read_timeouts` holds its read timeout, in the order that they came.
    `closed_before_reply` holds the first text of each request whose reply came after the client
    closed the connection.
    """

    def __init__(self, answer: Callable[[list[str], float | None], bytes]) -> None:
        self.answer = answer
        self.requests: list[list[str]] = []
        self.read_timeouts: list[float | None] = []
        self.closed_before_reply: list[str] = []
        self.lock = threading.Lock()

    def sent(self) -> list[str]:
        """The first text of each request, in the order that they came."""
        with self.lock:
            return [texts[0] for texts in self.requests]


class GatewayConnection(httpcore2.NetworkStream):
    """One connection to `Gateway`, in place of the socket that the dial of httpcore2 opens.

    The first read after a request gets the reply from the gateway. If the client closed the
    connection before the reply came, the read fails as a read on a closed socket fails: errno 9.
    """

    def __init__(self, gateway: Gateway) -> None:
        self._gateway = gateway
        self._request = bytearray()
        self._reply = b""
        self._closed = False

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self._request.extend(buffer)

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        if self._request:
            texts = request_texts(bytes(self._request))
            self._request.clear()
            with self._gateway.lock:
                self._gateway.requests.append(texts)
                self._gateway.read_timeouts.append(timeout)
            self._reply = self._gateway.answer(texts, timeout)
            if self._closed:
                with self._gateway.lock:
                    self._gateway.closed_before_reply.append(texts[0])
        if self._closed:
            raise httpcore2.ReadError("[Errno 9] Bad file descriptor")
        chunk, self._reply = self._reply[:max_bytes], self._reply[max_bytes:]
        return chunk

    def close(self) -> None:
        self._closed = True

    def get_extra_info(self, info: str) -> Any:
        return None


def dial_gateway(
    monkeypatch: pytest.MonkeyPatch,
    dns: DnsFake,
    answer: Callable[[list[str], float | None], bytes],
) -> Gateway:
    """Connect each dial of the HTTP client of the engine to one `Gateway`.

    The httpx2 client of the engine, its egress check and the connection pool of httpcore2 stay
    real. The host of the gateway URL answers a public address to the lookup of the connect, and
    only the socket under each connection is the gateway's.
    """
    gateway = Gateway(answer)
    dns.add(httpx2.URL(GATEWAY_URL).host, PUBLIC_ADDRESS)
    monkeypatch.setattr(
        httpcore2.SyncBackend,
        "connect_tcp",
        lambda _backend, *_args, **_kwargs: GatewayConnection(gateway),
    )
    return gateway


def wait_for(event: threading.Event, what: str) -> None:
    if not event.wait(THREAD_HANDOFF_BOUND_SECONDS):
        pytest.fail(f"The gateway waited {THREAD_HANDOFF_BOUND_SECONDS:g} s for {what}")
