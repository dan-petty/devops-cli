"""Tests for build_agent construction and per-request spend tracking."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from devops_cli.ai.client.factory import build_agent
from devops_cli.ai.spend.ledger import SpendLedger, track_request_spend
from devops_cli.github.request_scope import request_scope

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.otlp import FakeCollector


def _spend_rows(ledger: SpendLedger) -> Sequence[tuple[Any, ...]]:
    with contextlib.closing(sqlite3.connect(ledger.db_path)) as conn:
        rows: Sequence[tuple[Any, ...]] = conn.execute(
            "SELECT request_type, stage, provider, prompt_tokens > 0, completion_tokens > 0 "
            "FROM ai_spend_records"
        ).fetchall()
    return rows


def test_build_agent_creates_pydantic_ai_agent(model_fake: ModelFake) -> None:
    """build_agent constructs a native pydantic-ai Agent with instructions and tools."""

    def sample_tool(x: int) -> int:
        return x * 2

    agent = build_agent(
        task="chat",
        instructions="System instructions",
        tools=[sample_tool],
    )
    assert isinstance(agent, Agent)
    assert agent.model is model_fake


def test_build_agent_tracks_spend_for_each_model_request(
    model_fake: ModelFake, spend_ledger: SpendLedger
) -> None:
    """Every model request made by the agent records one entry in the spend ledger."""
    model_fake.answer("First reply")

    agent = build_agent(
        task="chat",
        request_type="chat_test",
        stage="chat",
    )
    res = agent.run_sync("Hello")
    assert res.output == "First reply"

    rows = _spend_rows(spend_ledger)
    assert len(rows) == 1
    assert rows[0][:3] == ("chat_test", "chat", "fake")


_GATEWAY_URL = "https://llm.example.com/v1"

_SERIES = (
    "devops_cli_ai_requests_total",
    "devops_cli_ai_tokens_total",
    "devops_cli_ai_spend_usd_total",
    "devops_cli_ai_model_answers_total",
)


def test_each_model_request_of_an_agent_adds_one_answer_count(
    model_fake: ModelFake, otlp: FakeCollector
) -> None:
    """A request of an agent that `build_agent` makes counts the model that answered it, as the
    run of an implement step does, so a stage or refine run shows a gateway fallback (#4475)."""
    model_fake.answer("First reply")

    build_agent(task="chat").run_sync("Hello")

    assert otlp.points("devops_cli_ai_model_answers_total") == [
        ({"asked": "fake-model", "answered": "fake-model", "fallback": "false", "row": "other"}, 1)
    ]


def test_the_ai_series_of_a_request_carry_the_job_row_that_sent_it(
    model_fake: ModelFake, otlp: FakeCollector
) -> None:
    """The request, token, spend and answer series of a request name the job row of the Service
    that sent it, so a query splits the tokens of stage from those of refine (#4475)."""
    model_fake.answer("First reply")

    with request_scope(row="stage"):
        build_agent(task="chat").run_sync("Hello")

    assert {
        name: sorted({attributes["row"] for attributes, _ in otlp.points(name)}) for name in _SERIES
    } == {name: ["stage"] for name in _SERIES}


def test_a_request_on_the_deepseek_group_costs_its_cached_and_new_input_and_its_output(
    spend_ledger: SpendLedger, config: Callable[..., Any]
) -> None:
    """A request of an agent gives the ledger the prompt tokens that the provider read from its
    cache, as the run of an implement step does (#4403). Of 1,000,000 prompt tokens, 900,000 come
    from the cache: 0.1 x 0.0784 + 0.9 x 0.002352 + 0.1 x 0.2352 USD for 100,000 completion
    tokens (#4475)."""
    deepseek = "deepseek-v4.1-flash-1017"
    config(k8s={"domain": "example.com"}, ai={"gateway_url": _GATEWAY_URL})

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[TextPart("ok")],
            usage=RequestUsage(
                input_tokens=1_000_000, cache_read_tokens=900_000, output_tokens=100_000
            ),
            model_name=deepseek,
        )

    model = FunctionModel(reply, model_name=deepseek)
    setattr(model, "served_by", _GATEWAY_URL)
    build_agent(model).run_sync("Hi")

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        (cost,) = conn.execute("SELECT cost_usd FROM ai_spend_records").fetchone()
    assert round(cost, 6) == 0.033477


def _durations(ledger: SpendLedger) -> list[float]:
    with contextlib.closing(sqlite3.connect(ledger.db_path)) as conn:
        rows = conn.execute("SELECT duration_seconds FROM ai_spend_records ORDER BY id").fetchall()
    return [row[0] for row in rows]


def _clock(monkeypatch: pytest.MonkeyPatch, *readings: float) -> None:
    """Give the hook of `build_agent` a monotonic clock that returns `readings` in order."""
    ticks = iter(readings)
    monkeypatch.setattr("devops_cli.ai.client.factory.monotonic", lambda: next(ticks))


def test_a_request_records_the_time_of_its_model_request(
    model_fake: ModelFake, spend_ledger: SpendLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record of a request holds the seconds between the start and the end of the model
    request on the monotonic clock, not the wall clock (#4504)."""
    model_fake.answer("First reply")
    _clock(monkeypatch, 10.0, 10.25)

    build_agent(task="chat").run_sync("Hello")

    assert _durations(spend_ledger) == [0.25]


def test_each_request_of_a_run_records_its_own_duration(
    spend_ledger: SpendLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run of two model requests writes two records, and the second does not reuse the
    duration of the first (#4504)."""
    calls = 0

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(parts=[ToolCallPart("lookup", {})])
        return ModelResponse(parts=[TextPart("done")])

    def lookup() -> str:
        return "found"

    agent = build_agent(FunctionModel(reply), tools=[lookup])
    _clock(monkeypatch, 1.0, 1.2, 2.0, 2.5)

    agent.run_sync("Hello")

    assert [round(seconds, 4) for seconds in _durations(spend_ledger)] == [0.2, 0.5]


def test_a_failed_model_request_writes_no_record_and_the_next_request_is_timed_from_its_start(
    spend_ledger: SpendLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model request that raises writes no record, and its start time does not carry to the
    next request (#4504)."""
    failing = True

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if failing:
            raise RuntimeError("model down")
        return ModelResponse(parts=[TextPart("ok")])

    agent = build_agent(FunctionModel(reply))
    _clock(monkeypatch, 5.0, 6.0, 7.5)
    with pytest.raises(RuntimeError, match="model down"):
        agent.run_sync("Hello")
    assert _durations(spend_ledger) == []

    failing = False
    agent.run_sync("Hello")

    assert _durations(spend_ledger) == [1.5]


def test_the_timed_record_keeps_the_fields_of_the_request(
    spend_ledger: SpendLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record that holds the duration also holds the provider, model, token counts, cache-read
    tokens, request type and stage of the request (#4504)."""

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[TextPart("ok")],
            usage=RequestUsage(input_tokens=100, cache_read_tokens=60, output_tokens=7),
        )

    _clock(monkeypatch, 0.0, 0.5)
    build_agent(
        FunctionModel(reply, model_name="timed-model"), request_type="chat_test", stage="analysis"
    ).run_sync("Hi")

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        row = conn.execute(
            "SELECT model, prompt_tokens, completion_tokens, request_type, stage, duration_seconds "
            "FROM ai_spend_records"
        ).fetchone()
    assert row == ("timed-model", 100, 7, "chat_test", "analysis", 0.5)


def test_the_backend_report_averages_the_recorded_durations(spend_ledger: SpendLedger) -> None:
    """The mean duration of a backend is the mean of the durations of its records (#4504)."""
    for seconds in (0.1, 0.3):
        track_request_spend(
            provider="gateway",
            model="m",
            server="example.com",
            served_by="http://backend.example.com",
            duration_seconds=seconds,
            ledger=spend_ledger,
        )

    report = spend_ledger.get_lifetime_report()

    assert [backend.mean_duration_seconds for backend in report.backends] == [0.2]
