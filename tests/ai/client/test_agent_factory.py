"""Tests for build_agent construction and per-request spend tracking."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from devops_cli.ai.client.factory import build_agent
from devops_cli.ai.spend.ledger import SpendLedger
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
