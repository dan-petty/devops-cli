"""Each gateway call records the backend that served it, for per-backend cost, time and quality,
and a hosted call is priced at the deployment model that the gateway names (#2031)."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.ai.client import LLMClient
from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.commands.ai_cost import app as cost_app
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from tests.llm_stream_fakes import route_llm_clients

runner = CliRunner()

GATEWAY_URL = "http://gateway.example.com:4000/v1"
REMOTE = "http://remote.example.com:8000/v1"
OLLAMA = "http://ollama-0.example.com:11434"
SERVED_BY_HEADER = "x-litellm-model-api-base"
# LiteLLM 1.103.0 names the deployment model of the route in this header, and the router writes
# the route name in the reply body (#2031).
SERVED_MODEL_HEADER = "x-litellm-model-name"
HOSTED_API = "https://api.openai.com"

# The ledger schema before the served_by column existed.
_PREVIOUS_SCHEMA = """
CREATE TABLE ai_spend_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    provider TEXT NOT NULL,
    server TEXT NOT NULL,
    backend_info TEXT,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    cached INTEGER NOT NULL DEFAULT 0,
    request_type TEXT NOT NULL DEFAULT 'chat',
    duration_seconds REAL NOT NULL DEFAULT 0.0
);
"""


@pytest.fixture(autouse=True)
def _public_endpoints(public_dns: str) -> None:
    """The configured endpoints are example.com URLs, which resolve to a public address."""


def _gateway_client(model: str = "devops-review") -> LLMClient:
    return LLMClient(
        AIConfig(provider="gateway", gateway_url=GATEWAY_URL, model=model),
        api_key="sk-gateway",
        cache_enabled=False,
    )


def _capture_spend(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "devops_cli.ai.spend.track_request_spend", lambda **kwargs: calls.append(kwargs)
    )
    return calls


def _record(ledger: SpendLedger, served_by: str | None, completion: int) -> None:
    ledger.record_request(
        provider="gateway",
        server="gateway.example.com:4000",
        model="devops-review",
        prompt_tokens=1000,
        completion_tokens=completion,
        cost_usd=0.0,
        served_by=served_by,
        duration_seconds=2.0,
    )


class TestLedger:
    def test_requests_are_grouped_by_serving_backend(self, tmp_path: Path) -> None:
        """Verify the report breaks gateway calls down by backend, with tokens per request."""
        ledger = SpendLedger(db_path=tmp_path / "spend.db")
        for served_by, completion in ((REMOTE, 100), (REMOTE, 300), (OLLAMA, 50), (None, 10)):
            _record(ledger, served_by, completion)

        report = ledger.get_lifetime_report()

        assert [
            (b.served_by, b.request_count, b.completion_tokens_per_request, b.models)
            for b in report.backends
        ] == [
            (REMOTE, 2, 200.0, ["devops-review"]),
            (OLLAMA, 1, 50.0, ["devops-review"]),
        ]

    def test_an_existing_ledger_gains_the_served_by_column(self, tmp_path: Path) -> None:
        """Verify a ledger written before served_by existed keeps its rows and records it."""
        db_path = tmp_path / "spend.db"
        with contextlib.closing(sqlite3.connect(db_path)) as conn, conn:
            conn.execute(_PREVIOUS_SCHEMA)
            conn.execute(
                "INSERT INTO ai_spend_records (timestamp, provider, server, model) "
                "VALUES ('2026-09-01T00:00:00+00:00', 'ollama', 'local', 'qwen')"
            )

        _record(SpendLedger(db_path=db_path), REMOTE, 100)

        with contextlib.closing(sqlite3.connect(db_path)) as conn:
            rows = conn.execute(
                "SELECT model, served_by FROM ai_spend_records ORDER BY id"
            ).fetchall()
        assert rows == [("qwen", None), ("devops-review", REMOTE)]


class TestClient:
    def test_gateway_response_records_its_serving_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the gateway's serving-backend header reaches the response and the ledger."""
        spend = _capture_spend(monkeypatch)

        body = {"choices": [{"message": {"content": "OK"}}], "usage": {"completion_tokens": 1}}
        route_llm_clients(
            monkeypatch,
            lambda request: httpx2.Response(200, json=body, headers={SERVED_BY_HEADER: REMOTE}),
        )

        reply = _gateway_client().chat("You are terse.", "Reply with OK.", use_cache=False)

        assert (reply.served_by, [c.get("served_by") for c in spend]) == (REMOTE, [REMOTE])

    def test_response_without_the_header_has_no_serving_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify providers other than the gateway record no serving backend rather than a guess."""
        spend = _capture_spend(monkeypatch)
        route_llm_clients(
            monkeypatch,
            lambda request: httpx2.Response(
                200, json={"choices": [{"message": {"content": "OK"}}]}
            ),
        )

        reply = _gateway_client().chat("You are terse.", "Reply with OK.", use_cache=False)

        assert (reply.served_by, [c.get("served_by") for c in spend]) == (None, [None])

    def test_streamed_response_records_its_serving_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify a streamed gateway reply records the backend named in its response headers."""
        spend = _capture_spend(monkeypatch)
        sse = b'data: {"choices": [{"delta": {"content": "OK"}}]}\n\ndata: [DONE]\n\n'

        def fake_send(self: Any, request: httpx2.Request, **kwargs: Any) -> httpx2.Response:
            headers = {SERVED_BY_HEADER: OLLAMA, "content-type": "text/event-stream"}
            return httpx2.Response(200, headers=headers, content=sse, request=request)

        monkeypatch.setattr(httpx2.Client, "send", fake_send)

        text = "".join(
            _gateway_client().chat_messages_stream(
                "You are terse.", [ChatMessage(role="user", content="Reply with OK.")]
            )
        )

        assert (text, [c.get("served_by") for c in spend]) == ("OK", [OLLAMA])


def _hosted_headers(served_model: str | None) -> dict[str, str]:
    """The headers of a gateway reply that a hosted API served, with the deployment model."""
    headers = {SERVED_BY_HEADER: HOSTED_API}
    if served_model is not None:
        headers[SERVED_MODEL_HEADER] = served_model
    return headers


def _chat_once(monkeypatch: pytest.MonkeyPatch, headers: dict[str, str]) -> None:
    """One blocking `devops-chat` call, with a reply that counts one million prompt tokens."""
    body = {
        "model": "devops-chat",
        "choices": [{"message": {"content": "OK"}}],
        "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0},
    }
    route_llm_clients(monkeypatch, lambda request: httpx2.Response(200, json=body, headers=headers))
    _gateway_client("devops-chat").chat("You are terse.", "Reply with OK.", use_cache=False)


def _stream_once(monkeypatch: pytest.MonkeyPatch, headers: dict[str, str]) -> None:
    """One streamed `devops-chat` call, whose headers arrive before the first chunk."""
    sse = b'data: {"model": "devops-chat", "choices": [{"delta": {"content": "OK"}}]}\n\n'
    sse += b"data: [DONE]\n\n"

    def fake_send(self: Any, request: httpx2.Request, **kwargs: Any) -> httpx2.Response:
        stream_headers = {**headers, "content-type": "text/event-stream"}
        return httpx2.Response(200, headers=stream_headers, content=sse, request=request)

    monkeypatch.setattr(httpx2.Client, "send", fake_send)
    "".join(
        _gateway_client("devops-chat").chat_messages_stream(
            "You are terse.", [ChatMessage(role="user", content="Reply with OK.")]
        )
    )


def _priced_rows(ledger: SpendLedger) -> list[tuple[Any, ...]]:
    with contextlib.closing(sqlite3.connect(ledger.db_path)) as conn:
        return conn.execute(
            "SELECT model, served_model, pricing_source, cost_usd > 0 FROM ai_spend_records"
            " ORDER BY id"
        ).fetchall()


@pytest.mark.parametrize("call", [_chat_once, _stream_once], ids=["blocking", "stream"])
@pytest.mark.parametrize(
    ("served_model", "priced"),
    [
        ("openai/gpt-4o", ("openai/gpt-4o", "genai_prices:openai", 1)),
        (None, (None, "unknown", 0)),
    ],
    ids=["names-the-deployment", "names-no-deployment"],
)
def test_a_hosted_gateway_reply_is_priced_at_the_deployment_model_that_it_names(
    monkeypatch: pytest.MonkeyPatch,
    spend_ledger: SpendLedger,
    call: Any,
    served_model: str | None,
    priced: tuple[Any, ...],
) -> None:
    """genai-prices does not know the route name `devops-chat`, so a hosted call cost $0 (#2031).

    A reply that names its deployment model is priced at that model, and the row keeps the route
    name as its model. A reply that names none is priced at the route name, as before.
    """
    call(monkeypatch, _hosted_headers(served_model))

    assert _priced_rows(spend_ledger) == [("devops-chat", *priced)]


def test_cost_command_breaks_spend_down_by_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops ai cost report --by backend` lists each serving backend."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    _record(ledger, REMOTE, 100)
    _record(ledger, OLLAMA, 40)
    monkeypatch.setattr("devops_cli.commands.ai_cost.get_spend_ledger", lambda: ledger)

    table = runner.invoke(cost_app, ["report", "--by", "backend"])
    as_json = runner.invoke(cost_app, ["report", "--by", "backend", "--json"])

    assert (
        table.exit_code,
        "remote.example.com:8000" in table.output,
        "ollama-0.example.com:11434" in table.output,
        [b["served_by"] for b in json.loads(as_json.output)["backends"]],
    ) == (0, True, True, [REMOTE, OLLAMA])


@pytest.mark.parametrize(
    ("served_by", "label"),
    [
        pytest.param(REMOTE, "remote.example.com:8000", id="url"),
        pytest.param("http://user:pw@example.com:11434", "example.com:11434", id="url-userinfo"),
        pytest.param("example.com:11434", "example.com:11434", id="bare-authority"),
        pytest.param("example.com:", "unknown", id="no-server"),
    ],
)
def test_cost_command_names_a_serving_backend_by_its_host_and_port(
    spend_ledger: SpendLedger, served_by: str, label: str
) -> None:
    """The table of `devops ai cost report --by backend` shows the host and port of a backend.

    It never shows the userinfo of a stored URL, and it shows `unknown` for a stored value that
    names no server.
    """
    _record(spend_ledger, served_by, 100)

    table = runner.invoke(cost_app, ["report", "--by", "backend"], env={"COLUMNS": "200"})

    shown = [
        line.split("devops-review")[0].strip()
        for line in table.output.splitlines()
        if "devops-review" in line
    ]
    assert (table.exit_code, shown) == (0, [label])
