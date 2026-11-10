"""One Jev model answers every request that it gets (#4319, #4309).

The HTTP client of a model belongs to an event loop. `httpx2.MockTransport` has no loop, so the
fake HTTP edge cannot show a request that runs on a closed loop. These tests send the requests to
a real server on loopback, which is an in-process server that `docs/TESTING.md` allows.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar, cast

import pytest
from pydantic_ai.models.decision import DecisionRequest, NoulAnswer, NoulQuestion

from devops_cli.ai import pydantic_ai_bridge
from devops_cli.ai.jev import create_jev_model, filter_rag_passages_with_jev
from devops_cli.config.settings import Settings

PASSAGES = ["The page is blank after Pay.", "The sky is blue."]


@pytest.fixture
def loopback_gateway(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Settings that point the gateway at a server on loopback that says `yes` to each question."""
    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _s: "sk-test")

    class Handler(BaseHTTPRequestHandler):
        # Keep-alive: the client keeps its connection, which belongs to the loop that opened it.
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            answer: dict[str, Any] = {
                "model": "typesafe/jev-1.14-20261014",
                "answers": {
                    name: {"type": "noul", "noul": 0.9, "confidence": 0.9}
                    for name in body["questions"]
                },
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
            payload = json.dumps(answer).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    settings = Settings()
    settings.ai.provider = "gateway"
    settings.ai.gateway_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    try:
        yield settings
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_a_helper_answers_twice_with_one_model(loopback_gateway: Settings) -> None:
    """Two calls of one helper on one model both return a ranking."""
    model = create_jev_model(settings=loopback_gateway)

    first = filter_rag_passages_with_jev("What broke?", PASSAGES, model=model)
    second = filter_rag_passages_with_jev("What broke?", PASSAGES, model=model)

    assert [len(first), len(second)] == [2, 2]


def test_the_public_function_answers_twice_with_one_model(loopback_gateway: Settings) -> None:
    """`decide_with_jev` returns the answer of each of two requests on one model."""
    from devops_cli.ai.jev import decide_with_jev

    model = create_jev_model(settings=loopback_gateway)
    request = DecisionRequest(
        state="The page is blank after Pay.",
        questions={"is_bug": NoulQuestion(instructions="Is this a software defect?")},
    )

    answers = [decide_with_jev(request, model=model).answers["is_bug"] for _ in range(2)]

    assert [(type(each), each.noul) for each in answers if isinstance(each, NoulAnswer)] == [
        (NoulAnswer, 0.9),
        (NoulAnswer, 0.9),
    ]


def test_the_public_function_builds_its_own_model_from_settings(
    loopback_gateway: Settings,
) -> None:
    """With no `model`, `decide_with_jev` builds the Jev model from `settings`, so a caller needs
    no private name and no loop of its own."""
    from devops_cli.ai.jev import decide_with_jev

    request = DecisionRequest(
        state="The page is blank after Pay.",
        questions={"is_bug": NoulQuestion(instructions="Is this a software defect?")},
    )

    first = decide_with_jev(request, settings=loopback_gateway)
    second = decide_with_jev(request, settings=loopback_gateway)

    assert (first.model_name, second.model_name) == ("typesafe/jev-1.14-20261014",) * 2


def test_the_public_function_raises_the_error_of_decide_and_runs_again(
    loopback_gateway: Settings,
) -> None:
    """A request that fails raises its own exception type, and the next request still runs."""
    from devops_cli.ai.jev import decide_with_jev

    class Failing:
        settings: ClassVar[dict[str, Any]] = {}

        async def decide(self, request: DecisionRequest, model_settings: Any) -> Any:
            raise ValueError("no answer")

    request = DecisionRequest(
        state="x", questions={"q": NoulQuestion(instructions="Is this a software defect?")}
    )
    with pytest.raises(ValueError, match="no answer"):
        decide_with_jev(request, model=cast(Any, Failing()))

    assert decide_with_jev(request, settings=loopback_gateway).answers.keys() == {"q"}


def test_the_call_settings_win_over_the_model_settings() -> None:
    """`decide` gets the model settings merged with the call settings, and the call wins."""
    from devops_cli.ai.jev import decide_with_jev

    seen: list[Any] = []

    class Recording:
        settings: ClassVar[dict[str, Any]] = {"temperature": 0.1, "timeout": 5.0}

        async def decide(self, request: DecisionRequest, model_settings: Any) -> Any:
            seen.append(dict(model_settings))
            return None

    request = DecisionRequest(state="x", questions={})
    decide_with_jev(request, model=cast(Any, Recording()), model_settings={"temperature": 0.7})

    assert seen == [{"temperature": 0.7, "timeout": 5.0}]
