"""The spend record of an agent run of a roadmap job (#2664): one ledger record for all the
replies of a run, under the stage of the task that served it."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Sequence
from typing import Any

import pytest
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelHTTPError,
    ModelTimeoutError,
    UnexpectedModelBehavior,
)
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.config.constants import CONST_ROADMAP_RUN_ERROR_CHARS
from devops_cli.roadmap.agent_run import (
    bounded_text,
    model_call_error,
    record_run_spend,
    run_error_message,
)

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


@pytest.mark.parametrize(
    ("raised", "kind", "status", "timed_out"),
    [
        (ModelHTTPError(504, "model", "MODEL-TEXT"), AIClientError, 504, False),
        (ModelTimeoutError("model", "timed out", body="MODEL-TEXT"), AIClientError, None, True),
        (ModelAPIError("model", "failed", body="MODEL-TEXT"), AIClientError, None, False),
        (ModelHTTPError(401, "model", "MODEL-TEXT"), AICredentialsError, None, False),
    ],
    ids=["status", "timeout", "neither", "refused-key"],
)
def test_a_failed_model_call_keeps_its_status_or_timeout_and_none_of_its_text(
    raised: ModelAPIError, kind: type[AIClientError], status: int | None, timed_out: bool
) -> None:
    error = model_call_error(raised, "The step's")

    assert (type(error), error.status, error.timed_out, "MODEL-TEXT" in str(error)) == (
        kind,
        status,
        timed_out,
        False,
    )


TOKEN = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"


@pytest.mark.parametrize(
    ("message", "logged"),
    [
        ("Exceeded maximum output retries (3)", "Exceeded maximum output retries (3)"),
        ("First line\ninput_value=MODEL-TEXT", "First line"),
        (f"The reply held {TOKEN} in it.", "The reply held <masked-github-token> in it."),
        (
            "Function tool calls must have unique `tool_call_id` values; "
            "duplicate `tool_call_id`s: ['MODEL-ID']",
            "Function tool calls must have unique <text> values",
        ),
        (
            "Tool 'MODEL-NAME' exceeded max retries count of 2: see https://example.com",
            "Tool <text> exceeded max retries count of 2",
        ),
        (
            "Cannot apply a delta to existing_part=TextPart('MODEL-TEXT')",
            "Cannot apply a delta to existing_part",
        ),
        ("a\x1b[2J\x00\x08\x7fb", "a[2Jb"),
        ("", ""),
    ],
    ids=["fixed", "first-line", "secret", "tool-call-id", "tool-name", "repr", "control", "empty"],
)
def test_the_message_of_a_stopped_run_keeps_its_fixed_description_only(
    message: str, logged: str
) -> None:
    """The text after the first `:`, `;`, `=` or quoted part can hold data that the model chose.
    The message loses it, the control characters and the secrets, and a later line."""
    assert run_error_message(UnexpectedModelBehavior(message, body="MODEL-TEXT")) == logged


def test_a_long_message_is_cut_to_the_limit() -> None:
    assert (
        len(run_error_message(UnexpectedModelBehavior("x" * 5000))) == CONST_ROADMAP_RUN_ERROR_CHARS
    )


def test_a_secret_is_masked_before_a_cut_can_split_it() -> None:
    text = "x" * (CONST_ROADMAP_RUN_ERROR_CHARS - 10) + TOKEN

    assert TOKEN[:20] not in bounded_text(text)
