"""The recorded replies of a real Valkey server, served on a loopback port the test binds (#4557, ADR 0007).

`RecordedValkey` serves the exchanges that `tests/support/valkey_recording.py` recorded for one
scenario, in their order, to a real valkey-py client: the client sends its own commands and reads
the recorded replies with its own parser, offline. A command that is not the next recorded one
gets an error reply and stays in `unexpected`, and `remaining` counts the replies that no command
took, so a test sees a client that sends other commands than the record holds.

An exchange holds the command, as the words of its RESP array, and the reply, as the RESP2 text
that the server sent. valkey-py speaks RESP2 unless a client asks for RESP3. The port is bound on
127.0.0.1 in the test's process, which the hermetic floor allows.

The RESP framing is the project's own, in about 30 lines. valkey-py and fakeredis keep their
parsers in private modules that read a socket and return values, not the bytes of one reply.
"""

from __future__ import annotations

import json
import socketserver
import threading
from collections.abc import Sequence
from importlib.resources import files
from typing import Any, BinaryIO

# The record of the scenarios' exchanges.
RECORD = files("tests").joinpath("fixtures", "valkey", "recorded_exchanges.json")
# The address that the replay and the recording proxy bind.
LOOPBACK = "127.0.0.1"
# How often a server's loop looks for its shutdown; `serve_forever` waits half a second by default.
SHUTDOWN_POLL_SECONDS = 0.01
_CRLF = b"\r\n"


def load_record() -> dict[str, Any]:
    """The recorded exchanges of every scenario, with the server and the valkey-py recorded."""
    record: dict[str, Any] = json.loads(RECORD.read_text(encoding="utf-8"))
    return record


def scenario_exchanges(name: str) -> list[dict[str, Any]]:
    """The recorded exchanges of one scenario."""
    exchanges: list[dict[str, Any]] = load_record()["scenarios"][name]
    return exchanges


def _line(stream: BinaryIO) -> bytes:
    """One RESP line with its CRLF; an empty result means that the peer closed the stream."""
    line = stream.readline()
    if line and not line.endswith(_CRLF):
        raise ValueError(f"a RESP line ends without CRLF: {line!r}")
    return line


def read_command(stream: BinaryIO) -> list[str] | None:
    """The words of the next command, an array of bulk strings; `None` once the peer closed."""
    header = _line(stream)
    if not header:
        return None
    if not header.startswith(b"*"):
        raise ValueError(f"a command is not a RESP array: {header!r}")
    words: list[str] = []
    for _ in range(int(header[1:])):
        size = _line(stream)
        if not size.startswith(b"$"):
            raise ValueError(f"a command word is not a bulk string: {size!r}")
        words.append(stream.read(int(size[1:]) + len(_CRLF))[: -len(_CRLF)].decode())
    return words


def read_reply(stream: BinaryIO) -> bytes:
    """The bytes of the next RESP2 reply: a status, error, integer, bulk string or array."""
    line = _line(stream)
    if not line:
        raise ConnectionError("the server closed the connection before it replied")
    kind, value = line[:1], line[1 : -len(_CRLF)]
    if kind in (b"+", b"-", b":"):
        return line
    if kind == b"$":
        return line if int(value) < 0 else line + stream.read(int(value) + len(_CRLF))
    if kind == b"*":
        return line + b"".join(read_reply(stream) for _ in range(max(int(value), 0)))
    raise ValueError(f"a reply is not RESP2: {line!r}")


def pack_command(words: Sequence[str]) -> bytes:
    """A command as valkey-py sends it: an array of bulk strings."""
    parts = [b"*%d\r\n" % len(words)]
    for word in words:
        data = word.encode()
        parts.append(b"$%d\r\n%s\r\n" % (len(data), data))
    return b"".join(parts)


class _ReplayServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True

    def __init__(self, valkey: RecordedValkey) -> None:
        super().__init__((LOOPBACK, 0), _ReplayHandler)
        self.valkey = valkey


class _ReplayHandler(socketserver.StreamRequestHandler):
    server: _ReplayServer

    def handle(self) -> None:
        while (command := read_command(self.rfile)) is not None:
            self.wfile.write(self.server.valkey.answer(command))


class RecordedValkey:
    """Serve one scenario's recorded replies, in order, on a loopback port."""

    def __init__(self, exchanges: Sequence[dict[str, Any]]) -> None:
        self._exchanges = list(exchanges)
        self._next = 0
        self._lock = threading.Lock()
        self.unexpected: list[str] = []
        self._server = _ReplayServer(self)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": SHUTDOWN_POLL_SECONDS},
            name="recorded-valkey",
            daemon=True,
        )

    @property
    def port(self) -> int:
        """The loopback port that a valkey-py client connects to."""
        port: int = self._server.server_address[1]
        return port

    @property
    def remaining(self) -> int:
        """How many recorded replies no command took."""
        return len(self._exchanges) - self._next

    def answer(self, command: list[str]) -> bytes:
        """The next recorded reply when the command is the next recorded one, else an error."""
        with self._lock:
            expected = self._exchanges[self._next] if self._next < len(self._exchanges) else None
            if expected and expected["command"] == command:
                self._next += 1
                reply: str = expected["reply"]
                return reply.encode()
            self.unexpected.append(" ".join(command))
        # The error names only the command, since a word of its arguments can hold a CRLF.
        return b"-ERR no recorded reply for %s\r\n" % " ".join(command[:1]).encode()

    def __enter__(self) -> RecordedValkey:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
