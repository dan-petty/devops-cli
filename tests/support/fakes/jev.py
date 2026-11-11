"""In-memory fake for the TypeSafe Jev decision edge (#4298, ADR 0007).

Doubles the `/v1/systemone` endpoint that `SystemOneModel` posts to. The fake is a transport under
the real model, so the request body is built and the answers are validated by the library for
real: an answer the real endpoint would not send fails the test the way it fails in production.
It answers every question of a request from the picks a test gives, records each request and
the event loop that sent it, fails a request on demand, and holds a request open until the test
releases it, without a socket.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx2
import pytest
from pydantic_ai.models.system_one import SystemOneModel
from pydantic_ai.profiles.typesafe import typesafe_model_profile
from pydantic_ai.providers.system_one import SystemOneProvider

from devops_cli.config.constants import CONST_AI_JEV_MODEL

_GATEWAY = "http://example.com:4000/v1"
_PICK_SHARE = 0.9
# The probability of a noul question that the test gives no pick for: a clear no.
_DEFAULT_NOUL = 0.02

Pick = str | int | float


def _spread(names: list[str], picked: str, confidence: float) -> dict[str, float]:
    """A distribution over `names` whose mode is `picked`, with the rest shared evenly."""
    rest = [name for name in names if name != picked]
    if not rest:
        return {picked: 1.0}
    share = round((1.0 - confidence) / len(rest), 4)
    return {**dict.fromkeys(rest, share), picked: round(1.0 - share * len(rest), 4)}


class JevFake:
    """The Jev endpoint. A test sets `picks`: a question name maps to the option a choice picks,
    the level a score picks, or the probability a noul answers. A question with no pick gets the
    first option, level 0, or a clear no. `confidence` is the confidence of every choice and
    score answer."""

    __test__ = False

    def __init__(self) -> None:
        self.picks: dict[str, Pick] = {}
        self.confidence: float = _PICK_SHARE
        self.requests: list[dict[str, Any]] = []
        self.status: int | None = None
        self.error: Exception | None = None
        self.loops: list[asyncio.AbstractEventLoop] = []
        self._held = False
        self._waiting: list[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = []
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self.model: SystemOneModel = SystemOneModel(
            CONST_AI_JEV_MODEL,
            provider=SystemOneProvider(
                api_key="sk-test",
                base_url=_GATEWAY,
                http_client=httpx2.AsyncClient(
                    transport=httpx2.MockTransport(self._handle), base_url=_GATEWAY
                ),
            ),
            profile=typesafe_model_profile(CONST_AI_JEV_MODEL),
        )

    def fail(self, status: int) -> None:
        """Answer every request with this HTTP status."""
        self.status = status

    def unreachable(self, error: Exception) -> None:
        """Raise this transport error for every request."""
        self.error = error

    def hold(self) -> None:
        """Keep every request open until `release`, as an endpoint that never answers does."""
        self._held = True

    def release(self) -> None:
        """Answer the held requests and hold no more. A thread other than the one that sends the
        requests can call it."""
        with self._lock:
            self._held = False
            for loop, answered in self._waiting:
                loop.call_soon_threadsafe(answered.set)

    async def _wait_while_held(self) -> None:
        with self._lock:
            if not self._held:
                return
            entry = (asyncio.get_running_loop(), asyncio.Event())
            self._waiting.append(entry)
        try:
            await entry[1].wait()
        finally:
            with self._lock:
                self._waiting.remove(entry)

    @property
    def asked(self) -> list[list[str]]:
        """The question names of each request, in order."""
        return [list(body["questions"]) for body in self.requests]

    def _answer(self, name: str, question: dict[str, Any]) -> dict[str, Any]:
        kind, pick = question["type"], self.picks.get(name)
        if kind == "noul":
            return {"type": "noul", "noul": float(pick if pick is not None else _DEFAULT_NOUL)}
        if kind == "choice":
            names = list(question["criteria"])
            chosen = str(pick) if pick is not None else names[0]
            probabilities = _spread(names, chosen, self.confidence)
            return {
                "type": "choice",
                "choice": chosen,
                "probabilities": probabilities,
                "confidence": self.confidence,
            }
        levels = [str(level) for level in range(len(question["criteria"]))]
        chosen_level = str(int(pick)) if pick is not None else levels[0]
        probabilities = _spread(levels, chosen_level, self.confidence)
        score = round(sum(int(level) * share for level, share in probabilities.items()), 2)
        return {
            "type": "score",
            "score": score,
            "probabilities": probabilities,
            "confidence": self.confidence,
        }

    def _reply(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """The status and the JSON of the endpoint's answer to a request body."""
        self.requests.append(body)
        if self.status is not None:
            return self.status, {"error": "the fake refuses"}
        answers = {name: self._answer(name, q) for name, q in body["questions"].items()}
        usage = {"input_tokens": 64, "output_tokens": len(answers)}
        return 200, {"model": CONST_AI_JEV_MODEL, "answers": answers, "usage": usage}

    async def _handle(self, request: httpx2.Request) -> httpx2.Response:
        self.loops.append(asyncio.get_running_loop())
        if self.error is not None:
            raise self.error
        await self._wait_while_held()
        status, payload = self._reply(json.loads(request.content))
        return httpx2.Response(status, json=payload)

    @property
    def url(self) -> str:
        """The `/v1` base URL of the loopback server, which `over_loopback` starts."""
        assert self._server is not None, "over_loopback starts the server"
        return f"http://127.0.0.1:{self._server.server_address[1]}/v1"

    def over_loopback(self) -> SystemOneModel:
        """A `SystemOneModel` that owns its HTTP client and talks to this fake over a socket on
        the loopback interface, which the test binds itself. Its connections stay open between
        requests, as those of the real model do. `close` stops the server."""
        fake = self

        class Endpoint(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:
                size = int(self.headers["Content-Length"])
                status, payload = fake._reply(json.loads(self.rfile.read(size)))
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args: Any) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return SystemOneModel(
            CONST_AI_JEV_MODEL,
            provider=SystemOneProvider(api_key="sk-test", base_url=self.url),
            profile=typesafe_model_profile(CONST_AI_JEV_MODEL),
        )

    def close(self) -> None:
        """Stop the loopback server, when one runs."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()


@pytest.fixture
def jev() -> Iterator[JevFake]:
    """The Jev edge, faked: a `SystemOneModel` over `JevFake` for the code under test to decide
    with."""
    fake = JevFake()
    yield fake
    fake.close()
