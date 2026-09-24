"""Each gateway call records the backend that served it, for per-backend cost, time and quality."""

from __future__ import annotations

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

runner = CliRunner()

GATEWAY_URL = "http://gateway.example.com:4000/v1"
VLLM = "http://vllm.example.com:8000/v1"
OLLAMA = "http://ollama-0.example.com:11434"
SERVED_BY_HEADER = "x-litellm-model-api-base"

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
def _allow_private_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")


def _gateway_client() -> LLMClient:
    return LLMClient(
        AIConfig(provider="gateway", gateway_url=GATEWAY_URL, model="devops-review"),
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
        for served_by, completion in ((VLLM, 100), (VLLM, 300), (OLLAMA, 50), (None, 10)):
            _record(ledger, served_by, completion)

        report = ledger.get_lifetime_report()

        assert [
            (b.served_by, b.request_count, b.completion_tokens_per_request, b.models)
            for b in report.backends
        ] == [
            (VLLM, 2, 200.0, ["devops-review"]),
            (OLLAMA, 1, 50.0, ["devops-review"]),
        ]

    def test_an_existing_ledger_gains_the_served_by_column(self, tmp_path: Path) -> None:
        """Verify a ledger written before served_by existed keeps its rows and records it."""
        db_path = tmp_path / "spend.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(_PREVIOUS_SCHEMA)
            conn.execute(
                "INSERT INTO ai_spend_records (timestamp, provider, server, model) "
                "VALUES ('2026-09-01T00:00:00+00:00', 'ollama', 'local', 'qwen')"
            )

        _record(SpendLedger(db_path=db_path), VLLM, 100)

        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT model, served_by FROM ai_spend_records ORDER BY id"
            ).fetchall()
        assert rows == [("qwen", None), ("devops-review", VLLM)]


class TestClient:
    def test_gateway_response_records_its_serving_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the gateway's serving-backend header reaches the response and the ledger."""
        spend = _capture_spend(monkeypatch)

        def fake_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
            body = {"choices": [{"message": {"content": "OK"}}], "usage": {"completion_tokens": 1}}
            return httpx2.Response(
                200,
                json=body,
                headers={SERVED_BY_HEADER: VLLM},
                request=httpx2.Request("POST", url),
            )

        monkeypatch.setattr(httpx2.Client, "post", fake_post)

        reply = _gateway_client().chat("You are terse.", "Reply with OK.", use_cache=False)

        assert (reply.served_by, [c.get("served_by") for c in spend]) == (VLLM, [VLLM])

    def test_response_without_the_header_has_no_serving_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify providers other than the gateway record no serving backend rather than a guess."""
        spend = _capture_spend(monkeypatch)
        monkeypatch.setattr(
            httpx2.Client,
            "post",
            lambda self, url, **kw: httpx2.Response(
                200,
                json={"choices": [{"message": {"content": "OK"}}]},
                request=httpx2.Request("POST", url),
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
            return httpx2.Response(
                200, headers={SERVED_BY_HEADER: OLLAMA}, content=sse, request=request
            )

        monkeypatch.setattr(httpx2.Client, "send", fake_send)

        text = "".join(
            _gateway_client().chat_messages_stream(
                "You are terse.", [ChatMessage(role="user", content="Reply with OK.")]
            )
        )

        assert (text, [c.get("served_by") for c in spend]) == ("OK", [OLLAMA])


def test_cost_command_breaks_spend_down_by_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops ai cost report --by backend` lists each serving backend."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    _record(ledger, VLLM, 100)
    _record(ledger, OLLAMA, 40)
    monkeypatch.setattr("devops_cli.commands.ai_cost.get_spend_ledger", lambda: ledger)

    table = runner.invoke(cost_app, ["report", "--by", "backend"])
    as_json = runner.invoke(cost_app, ["report", "--by", "backend", "--json"])

    assert (
        table.exit_code,
        "vllm.example.com:8000" in table.output,
        "ollama-0.example.com:11434" in table.output,
        [b["served_by"] for b in json.loads(as_json.output)["backends"]],
    ) == (0, True, True, [VLLM, OLLAMA])
