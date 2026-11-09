"""Tests for build_agent construction and per-request spend tracking."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent

from devops_cli.ai.client.factory import build_agent
from devops_cli.ai.spend.ledger import SpendLedger

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake


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
