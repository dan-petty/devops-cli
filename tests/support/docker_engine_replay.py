"""The Engine API's recorded answers, served on a Unix socket the test binds (#1316, ADR 0007).

`RecordedEngine` serves the exchanges that `tests/support/docker_engine_recording.py` recorded for
one scenario, in their order, to a real `docker.DockerClient`: the SDK sends its own requests and
reads the recorded replies with its own code, offline. A request that is not the next recorded one
gets a 500 reply and stays in `unexpected`, and `remaining` counts the replies no request took, so
a test sees an SDK that sends other requests than the recording holds.

A reply is sent as the engine sent it: with a length, in chunks (a stream of JSON entries or log
frames), or after `101 UPGRADED` as raw frames on the socket, as the engine answers an exec. The
SDK reads an upgraded reply from the socket under the HTTP reader, so the raw frames go out after
a short pause, once the reader has taken the status line and the headers.

The socket is bound in the test's process, which the hermetic floor allows, in a new directory
under the test's own temporary directory.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import socketserver
import tempfile
import threading
import time
from collections.abc import Iterator, Sequence
from importlib.resources import files
from pathlib import Path
from typing import Any

import h11

# The record of the scenarios' exchanges.
RECORD = files("tests").joinpath("fixtures", "docker_engine", "recorded_exchanges.json")
# The longest Unix socket path, in bytes, that `bind` and `connect` take on Linux.
UNIX_PATH_BYTES = 107
# How long the server waits after `101 UPGRADED` before it sends the raw frames.
UPGRADE_PAUSE_SECONDS = 0.05
# How often a server's loop looks for its shutdown; `serve_forever` waits half a second by default.
SHUTDOWN_POLL_SECONDS = 0.01
_RECEIVE_BYTES = 65_536


def load_record() -> dict[str, Any]:
    """The recorded exchanges of every scenario, with the SDK and engine that were recorded."""
    record: dict[str, Any] = json.loads(RECORD.read_text(encoding="utf-8"))
    return record


def body_bytes(exchange: dict[str, Any]) -> list[bytes]:
    """The recorded reply body of an exchange, as the chunks the engine sent."""
    body = exchange.get("body")
    if body is None:
        return []
    kind, value = body["kind"], body["value"]
    if kind == "json":
        return [json.dumps(value).encode() + b"\n"]
    if kind == "json_lines":
        return [json.dumps(entry).encode() + b"\n" for entry in value]
    if kind == "text":
        return [str(value).encode()]
    return [base64.b64decode(value)]


def events(conn: h11.Connection, sock: socket.socket) -> Iterator[Any]:
    """The events of a connection, read from the socket whenever h11 needs more bytes."""
    while True:
        event = conn.next_event()
        if event is h11.NEED_DATA:
            conn.receive_data(sock.recv(_RECEIVE_BYTES))
            continue
        yield event


def read_request(conn: h11.Connection, sock: socket.socket) -> tuple[h11.Request | None, bytes]:
    """The next request on a connection and its body; `None` once the peer closed it."""
    request: h11.Request | None = None
    body = bytearray()
    for event in events(conn, sock):
        if isinstance(event, h11.Request):
            request = event
            continue
        if isinstance(event, h11.Data):
            body.extend(event.data)
            continue
        if isinstance(event, h11.EndOfMessage):
            return request, bytes(body)
        break
    return None, b""


def send_reply(conn: h11.Connection, sock: socket.socket, exchange: dict[str, Any]) -> bool:
    """Send a recorded reply; return whether the connection can take another request."""
    headers = [(name, value) for name, value in exchange["headers"].items()]
    chunks = body_bytes(exchange)
    framing = exchange["framing"]
    if framing == "upgrade":
        upgrade = [("Connection", "Upgrade"), ("Upgrade", "tcp")]
        sock.sendall(
            conn.send(h11.InformationalResponse(status_code=101, headers=headers + upgrade))
        )
        time.sleep(UPGRADE_PAUSE_SECONDS)
        sock.sendall(b"".join(chunks))
        return False
    if framing == "chunked":
        headers.append(("Transfer-Encoding", "chunked"))
    else:
        headers.append(("Content-Length", str(sum(len(chunk) for chunk in chunks))))
    sock.sendall(conn.send(h11.Response(status_code=exchange["status"], headers=headers)))
    for chunk in chunks:
        if chunk:
            sock.sendall(conn.send(h11.Data(data=chunk)))
    sock.sendall(conn.send(h11.EndOfMessage()))
    return conn.our_state is h11.DONE and conn.their_state is h11.DONE


def short_socket_dir(prefix: str) -> Path:
    """A new directory for a socket under the temporary directory, which pytest keeps short.

    A Unix socket path holds at most `UNIX_PATH_BYTES` bytes; a longer one fails here, by name.
    """
    directory = Path(tempfile.mkdtemp(prefix=prefix))
    if len(os.fsencode(directory / "engine.sock")) > UNIX_PATH_BYTES:
        directory.rmdir()
        raise RuntimeError(f"a socket under {directory} would pass {UNIX_PATH_BYTES} bytes")
    return directory


class _ReplayServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def __init__(self, path: Path, engine: RecordedEngine) -> None:
        super().__init__(str(path), _ReplayHandler)
        self.engine = engine


class _ReplayHandler(socketserver.BaseRequestHandler):
    server: _ReplayServer

    def handle(self) -> None:
        engine = self.server.engine
        conn = h11.Connection(h11.SERVER)
        while True:
            request, _ = read_request(conn, self.request)
            if request is None:
                return
            reply = engine.answer(request)
            try:
                if not send_reply(conn, self.request, reply):
                    return
            except BrokenPipeError, ConnectionResetError:
                # The SDK closes a stats stream after the frames it wants; nothing reads the rest.
                return
            conn.start_next_cycle()


class RecordedEngine:
    """Serve one scenario's recorded exchanges, in order, on a Unix socket."""

    def __init__(self, exchanges: Sequence[dict[str, Any]]) -> None:
        self._exchanges = list(exchanges)
        self._next = 0
        self._lock = threading.Lock()
        self.unexpected: list[str] = []
        self._dir = short_socket_dir("dke")
        self.path = self._dir / "engine.sock"
        self._server = _ReplayServer(self.path, self)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": SHUTDOWN_POLL_SECONDS},
            name="recorded-docker-engine",
            daemon=True,
        )

    @property
    def base_url(self) -> str:
        """The endpoint a docker SDK client takes: `unix://` and the socket path."""
        return f"unix://{self.path}"

    @property
    def remaining(self) -> int:
        """How many recorded replies no request took."""
        return len(self._exchanges) - self._next

    def answer(self, request: h11.Request) -> dict[str, Any]:
        """The next recorded reply when the request is the next recorded one, else a 500."""
        method, target = request.method.decode(), request.target.decode()
        with self._lock:
            expected = self._exchanges[self._next] if self._next < len(self._exchanges) else None
            if expected and (expected["method"], expected["target"]) == (method, target):
                self._next += 1
                return expected
            self.unexpected.append(f"{method} {target}")
        message = {"message": f"no recorded reply for {method} {target}"}
        return {
            "status": 500,
            "headers": {"Content-Type": "application/json"},
            "framing": "length",
            "body": {"kind": "json", "value": message},
        }

    def __enter__(self) -> RecordedEngine:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
        shutil.rmtree(self._dir, ignore_errors=True)


def scenario_exchanges(name: str) -> list[dict[str, Any]]:
    """The recorded exchanges of one scenario."""
    exchanges: list[dict[str, Any]] = load_record()["scenarios"][name]
    return exchanges
