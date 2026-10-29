"""The spend record of an agent run of a roadmap job (#2664): one ledger record for all the
replies of a run, under the stage of the task that served it."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Sequence
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage

from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.roadmap.agent_run import record_run_spend

pytestmark = pytest.mark.usefixtures("keyring_store")


def _reply(input_tokens: int, output_tokens: int) -> ModelResponse:
    return ModelResponse(
        parts=[TextPart("ok")],
        usage=RequestUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _rows(ledger: SpendLedger) -> Sequence[tuple[Any, ...]]:
    with contextlib.closing(sqlite3.connect(ledger.db_path)) as conn:
        rows: Sequence[tuple[Any, ...]] = conn.execute(
            "SELECT request_type, stage, prompt_tokens, completion_tokens FROM ai_spend_records"
        ).fetchall()
    return rows


def test_the_replies_of_a_run_make_one_record_under_the_stage_of_the_task(
    spend_ledger: SpendLedger,
) -> None:
    messages: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart("go")]),
        _reply(100, 7),
        ModelRequest(parts=[UserPromptPart("again")]),
        _reply(150, 9),
    ]

    record_run_spend(FunctionModel(lambda m, i: _reply(1, 1)), messages, 1.5, stage="implement")

    assert _rows(spend_ledger) == [("agent_run", "implement", 250, 16)]


def test_a_run_with_no_reply_makes_no_record(spend_ledger: SpendLedger) -> None:
    record_run_spend(
        FunctionModel(lambda m, i: _reply(1, 1)),
        [ModelRequest(parts=[UserPromptPart("go")])],
        0.1,
        stage="implement",
    )

    assert _rows(spend_ledger) == []
