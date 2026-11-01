"""The output cap and the deadline of a model call in a step (#2869).

A fake server answers the requests of the real gateway model (`resolve_pydantic_ai_model`) as an
OpenAI-compatible server in front of Ollama does: it streams a reply token by token, and it ends
the reply with the finish reason `length` when the request names a cap and the reply is longer.
So a model that never stops is cut by the cap that the step sends, and no test reaches a network.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic_ai.messages import ModelResponse

from devops_cli.ai import pydantic_ai_bridge
from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS,
    CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import Settings
from devops_cli.exceptions.ai_pydantic import OutputCapReached, UnexpectedModelBehavior
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.roadmap import implement_step
from devops_cli.roadmap.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.llm_stream_fakes import OPENAI_DONE, SSE, sse_data
from tests.support.fakes.process import ProcessFake
from tests.support.implement_step import WINDOW, git, is_clean_at, the_whole_group
from tests.support.model_script import Hang, ModelScript, say
from tests.web_fakes import StubWeb

pytestmark = pytest.mark.usefixtures("keyring_store")

GATEWAY_URL = "http://example.com:4000/v1"
CAP = CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS
# The cap of the tests that stream a whole reply: the fake server sends one event for each token,
# so the real cap would take seconds. The tests send the constant of the module, not the number.
SMALL_CAP = 300
# Where the fake server cuts a reply when the request names no cap, so a test of a missing cap ends.
SERVER_DEFAULT_TOKENS = 3 * SMALL_CAP
CAP_REASON = (
    f"OutputCapReached: The model reply reached the output cap of {SMALL_CAP} tokens, "
    "so the call ended."
)


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


@pytest.fixture
def small_cap(monkeypatch: pytest.MonkeyPatch) -> int:
    """The step with a cap that a test can stream whole."""
    monkeypatch.setattr(implement_step, "CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS", SMALL_CAP)
    return SMALL_CAP


@pytest.fixture(autouse=True)
def _public_endpoints(public_dns: str) -> None:
    """The gateway is an example.com URL, which resolves to a public address."""


@dataclass(frozen=True)
class Reply:
    """What the fake model says. `calls` are tool calls `(tool, arguments)`; the first call gets
    `content_tokens` tokens of filler as its `content`. `text` is a text reply. With `endless`,
    the model never stops: it writes on in the last call, or in its text when it has no call."""

    calls: tuple[tuple[str, dict[str, Any]], ...] = ()
    text: str = ""
    content_tokens: int = 0
    endless: bool = False


def _pieces(text: str) -> list[str]:
    """`text` in pieces of 4 characters, each of which the fake server counts as one token."""
    return [text[position : position + 4] for position in range(0, len(text), 4)]


def _call_delta(index: int, function: dict[str, str], *, name: str | None = None) -> dict[str, Any]:
    head = {"id": f"call_{index}", "type": "function"} if name else {}
    return {"tool_calls": [{"index": index, **head, "function": function}]}


def _call_tokens(reply: Reply, index: int, tool: str, arguments: dict[str, Any]) -> Iterator[Any]:
    """The deltas of one tool call, one for each token."""
    if index == 0 and reply.content_tokens:
        arguments = {**arguments, "content": "x" * 4 * reply.content_tokens}
    last = index == len(reply.calls) - 1
    text = json.dumps(arguments)
    text = text[:-2] if reply.endless and last else text
    first, *rest = _pieces(text)
    yield _call_delta(index, {"name": tool, "arguments": first}, name=tool)
    for piece in rest:
        yield _call_delta(index, {"arguments": piece})
    if reply.endless and last:
        for _ in itertools.count():
            yield _call_delta(index, {"arguments": "xxxx"})


def _tokens(reply: Reply) -> Iterator[Any]:
    """The deltas of a reply, one for each token. An endless reply has no last one."""
    for piece in _pieces(reply.text):
        yield {"content": piece}
    if reply.endless and not reply.calls:
        for _ in itertools.count():
            yield {"content": "word "}
    for index, (tool, arguments) in enumerate(reply.calls):
        yield from _call_tokens(reply, index, tool, arguments)


def _chunk(delta: dict[str, Any], finish_reason: str | None = None) -> bytes:
    return sse_data(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "devops-coder",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
    )


async def _frames(reply: Reply, cap: int) -> AsyncIterator[bytes]:
    """The stream of a reply: at most `cap` tokens, then the finish reason `length`."""
    sent = 0
    for delta in _tokens(reply):
        if sent >= cap:
            yield _chunk({}, "length")
            yield OPENAI_DONE
            return
        yield _chunk(delta)
        sent += 1
        await asyncio.sleep(0)
    yield _chunk({}, "tool_calls" if reply.calls else "stop")
    yield OPENAI_DONE


class FakeServer:
    """The fake OpenAI-compatible server: it answers the nth chat request with the nth reply, and
    the last reply for every request after that. It keeps the body of each request."""

    def __init__(self, *replies: Reply) -> None:
        self.replies = replies
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response | None:
        if not request.url.path.endswith("/chat/completions"):
            return None
        body = json.loads(request.content)
        self.bodies.append(body)
        reply = self.replies[min(len(self.bodies), len(self.replies)) - 1]
        cap = body.get("max_completion_tokens", SERVER_DEFAULT_TOKENS)
        return httpx2.Response(200, headers={"content-type": SSE}, content=_frames(reply, cap))


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch, stub_web: StubWeb) -> Any:
    """Make the gateway model of the roadmap service, and the way to serve it: call the result
    with the replies of the fake model to get the model and its server."""
    monkeypatch.setattr(pydantic_ai_bridge, "_is_testing_mode_active", lambda: False)
    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _settings: "sk-gateway")
    settings = Settings()
    settings.ai.provider = "gateway"
    settings.ai.gateway_url = GATEWAY_URL

    def serve(*replies: Reply) -> tuple[Any, FakeServer]:
        server = FakeServer(*replies)
        stub_web.serve(server)
        model = pydantic_ai_bridge.resolve_pydantic_ai_model("devops-coder", settings=settings)
        return model, server

    return serve


def _step(store: InMemoryRoadmapStore, checkout: Path, model: Any) -> StepOutcome:
    return run_step(store, item=1, group=1, source=checkout, model=model, window=WINDOW)


# ── The settings of a call ────────────────────────────────────────────────────────────────


def test_the_first_request_holds_the_cap_and_the_deadline(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(say("Nothing to do."))

    _step(store, checkout, script.model())

    settings = script.settings_seen[0]
    assert (settings["max_tokens"], settings["request_timeout"]) == (
        CAP,
        CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS,
    )


def test_the_cap_reaches_the_gateway_as_max_completion_tokens_and_the_deadline_stays_local(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, served: Any
) -> None:
    model, server = served(Reply(text="Nothing to do."))

    _step(store, checkout, model)

    body = server.bodies[0]
    assert body["max_completion_tokens"] == CAP
    assert "request_timeout" not in body


# ── A reply that the cap ends ─────────────────────────────────────────────────────────────


def test_a_model_that_never_ends_a_text_reply_is_cut_at_the_cap_and_the_step_names_the_cause(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    served: Any,
    small_cap: int,
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    model, server = served(Reply(text="I will start.", endless=True))

    outcome = _step(store, checkout, model)

    assert (outcome.status, outcome.reason, outcome.requests, len(server.bodies)) == (
        StepStatus.STOPPED,
        CAP_REASON,
        1,
        1,
    )
    assert is_clean_at(checkout, head)


def test_a_tool_call_that_the_cap_cuts_stops_the_step_with_the_same_cause(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    served: Any,
    small_cap: int,
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    model, server = served(
        Reply(calls=(("write_file", {"path": "src/big.py", "content": ""}),), endless=True)
    )

    outcome = _step(store, checkout, model)

    assert (outcome.status, outcome.reason, outcome.requests, len(server.bodies)) == (
        StepStatus.STOPPED,
        CAP_REASON,
        1,
        1,
    )
    assert (outcome.diff, is_clean_at(checkout, head)) == ("", True), "the cut call ran"


def test_a_cut_reply_after_other_replies_names_the_cap_and_keeps_the_counts(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    served: Any,
    small_cap: int,
) -> None:
    refused = Reply(calls=(("shell", {"command": "pytest tests/test_sample.py"}),))
    model, _ = served(refused, Reply(text="Now I think.", endless=True))

    outcome = _step(store, checkout, model)

    assert outcome.reason == f"{CAP_REASON}\nRefused commands: pytest 1. Other retries: 0."


def test_a_reply_of_three_quarters_of_the_cap_passes(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    served: Any,
    small_cap: int,
) -> None:
    """A reply that stays under the cap is not cut. The test streams a whole file of three quarters
    of a small cap: the fake server sends one event for each token, so the real cap of 16,384
    tokens would take about 20 seconds. The real cap is 8 times the longest honest reply."""
    big = Reply(
        calls=(("write_file", {"path": "tests/test_big_reply.py", "content": ""}),),
        content_tokens=small_cap * 3 // 4,
    )
    group = Reply(calls=tuple(the_whole_group()))
    model, server = served(big, group, Reply(text="The group is done."))

    outcome = _step(store, checkout, model)

    assert (outcome.status, outcome.reason, len(server.bodies)) == (StepStatus.DONE, "", 3)
    assert "tests/test_big_reply.py" in git(checkout, "show", "--name-only", "--format=", "HEAD")


# ── A call that the deadline ends ─────────────────────────────────────────────────────────


def test_a_call_that_never_answers_ends_at_the_deadline_with_no_second_request(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(implement_step, "CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS", 0.2)
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(Hang())
    model = script.model()

    outcome = _step(store, checkout, model)

    assert (outcome.status, outcome.reason, len(script.seen)) == (
        StepStatus.STOPPED,
        f"ModelRequestTimeout: model {model.model_name}, no complete reply in 0.2 seconds",
        1,
    )
    assert is_clean_at(checkout, head)


def test_a_call_that_keeps_streaming_ends_at_the_deadline_with_no_second_request(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    served: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `timeout` setting limits only the wait for each chunk, so a model that sends a chunk
    all the time would never trip it. The deadline is one clock over the whole call: it ends this
    call, which the cap cannot end because the cap is out of reach."""
    monkeypatch.setattr(implement_step, "CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(implement_step, "CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS", 10**9)
    head = git(checkout, "rev-parse", "HEAD")
    model, server = served(Reply(text="I will start.", endless=True))

    outcome = _step(store, checkout, model)

    assert (outcome.status, outcome.reason, len(server.bodies)) == (
        StepStatus.STOPPED,
        f"ModelRequestTimeout: model {model.model_name}, no complete reply in 0.2 seconds",
        1,
    )
    assert is_clean_at(checkout, head)


# ── The error of a capped reply ───────────────────────────────────────────────────────────


def test_the_error_of_a_capped_reply_is_a_domain_error_with_its_own_code() -> None:
    message = "The model reply reached the output cap."
    error = OutputCapReached(message, response=ModelResponse(parts=[]))

    assert (error.error_code, error.message) == ("OUTPUT_CAP_REACHED", message)
    assert isinstance(error, DevOpsCLIError)
    assert isinstance(error, UnexpectedModelBehavior)
