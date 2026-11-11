"""The spend record of an agent run of a roadmap job (#2664): one ledger record for all the
replies of a run, under the stage of the task that served it."""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
from collections.abc import Callable, Sequence
from typing import Any

import pytest
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelHTTPError,
    ModelTimeoutError,
    UnexpectedModelBehavior,
)
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.config.constants import (
    CONST_ROADMAP_RUN_ERROR_CHARS,
    CONST_ROADMAP_RUN_TRACE_ARGUMENT_CHARS,
)
from devops_cli.roadmap.agent_run import (
    RunTrace,
    ToolCallRecord,
    bounded_text,
    model_call_error,
    record_run_spend,
    run_error_message,
)
from tests.support.fakes.otlp import FakeCollector

try:
    from devops_cli.roadmap.agent_run import TraceFacts
except ImportError:
    TraceFacts = None  # type: ignore[misc,assignment]

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
        (
            ModelTimeoutError("model", "timed out", body="MODEL-TEXT"),
            AIClientError,
            None,
            True,
        ),
        (
            ModelAPIError("model", "failed", body="MODEL-TEXT"),
            AIClientError,
            None,
            False,
        ),
        (ModelHTTPError(401, "model", "MODEL-TEXT"), AICredentialsError, None, False),
    ],
    ids=["status", "timeout", "neither", "refused-key"],
)
def test_a_failed_model_call_keeps_its_status_or_timeout_and_none_of_its_text(
    raised: ModelAPIError,
    kind: type[AIClientError],
    status: int | None,
    timed_out: bool,
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
        (
            f"The reply held {TOKEN} in it.",
            "The reply held <masked-github-token> in it.",
        ),
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
    ids=[
        "fixed",
        "first-line",
        "secret",
        "tool-call-id",
        "tool-name",
        "repr",
        "control",
        "empty",
    ],
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


def _tool_reply(input_tokens: int, output_tokens: int, *parts: ToolCallPart) -> ModelResponse:
    return ModelResponse(
        parts=list(parts),
        usage=RequestUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def test_a_trace_holds_the_tool_calls_and_the_counts_of_a_run() -> None:
    """The output tool is no tool call of the toolbox, and the counts sum all replies."""
    messages: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart("go")]),
        _tool_reply(
            100,
            7,
            ToolCallPart("read_file", {"path": "src/a.py"}),
            ToolCallPart("search_code", {"text": "needle"}),
        ),
        _tool_reply(150, 9, ToolCallPart("final_result", {"x": 1})),
    ]
    trace = RunTrace()

    trace.absorb(messages, tools={"read_file", "search_code"})

    assert (
        [(call.name, call.argument) for call in trace.tool_calls],
        trace.requests,
        trace.input_tokens,
        trace.output_tokens,
    ) == (
        [("read_file", '{"path":"src/a.py"}'), ("search_code", '{"text":"needle"}')],
        2,
        250,
        16,
    )


def test_a_trace_masks_and_cuts_the_argument_of_a_call() -> None:
    messages: list[ModelMessage] = [
        _tool_reply(1, 1, ToolCallPart("search_code", {"text": TOKEN})),
        _tool_reply(1, 1, ToolCallPart("search_code", {"text": "x" * 5000})),
    ]
    trace = RunTrace()

    trace.absorb(messages, tools={"search_code"})

    first, second = (call.argument for call in trace.tool_calls)
    assert (TOKEN in first, "<masked-github-token>" in first, len(second)) == (
        False,
        True,
        CONST_ROADMAP_RUN_TRACE_ARGUMENT_CHARS,
    )


def test_a_trace_masks_the_value_of_an_argument_by_its_name() -> None:
    """A value under a secret-suggesting name never reaches the trace, whatever its form (#3222).

    `mask_secrets` finds a secret by its form, so `opaque-value` would pass. The name masks it.
    """
    messages: list[ModelMessage] = [
        _tool_reply(
            1,
            1,
            ToolCallPart(
                "call_api",
                {
                    "path": "/v1/a",
                    "api_key": "opaque-value",
                    "nested": {"password": "hunter2"},
                },
            ),
            ToolCallPart("call_api", '{"bearer": "opaque-value", "path": "/v1/b"}'),
        ),
    ]
    trace = RunTrace()

    trace.absorb(messages, tools={"call_api"})

    assert [call.argument for call in trace.tool_calls] == [
        '{"path":"/v1/a","api_key":"<redacted>","nested":{"password":"<redacted>"}}',
        '{"bearer":"<redacted>","path":"/v1/b"}',
    ]


def test_a_trace_masks_an_argument_that_is_not_json_by_its_form() -> None:
    """An argument text that no JSON object holds has no names, so the masking by form applies."""
    messages: list[ModelMessage] = [
        _tool_reply(1, 1, ToolCallPart("call_api", f"not json {TOKEN}")),
    ]
    trace = RunTrace()

    trace.absorb(messages, tools={"call_api"})

    (argument,) = (call.argument for call in trace.tool_calls)
    assert (TOKEN in argument, "<masked-github-token>" in argument) == (False, True)


def test_a_trace_counts_the_violations_of_the_last_retry_prompt_of_the_output_tool() -> None:
    errors: list[Any] = [
        {"type": "missing", "loc": ("a",), "msg": "Field required", "input": {}},
        {"type": "missing", "loc": ("b",), "msg": "Field required", "input": {}},
    ]
    messages: list[ModelMessage] = [
        ModelRequest(parts=[RetryPromptPart(content=errors[:1], tool_name="final_result")]),
        ModelRequest(parts=[RetryPromptPart(content=errors, tool_name="final_result")]),
        ModelRequest(parts=[RetryPromptPart(content=errors[:1], tool_name="read_file")]),
    ]
    trace = RunTrace()

    trace.absorb(messages, tools={"read_file"})

    assert trace.violations == 2


def test_a_trace_of_no_reply_is_empty() -> None:
    trace = RunTrace()

    trace.absorb([ModelRequest(parts=[UserPromptPart("go")])], tools=set())

    assert (trace.tool_calls, trace.requests, trace.violations) == ([], 0, 0)


def test_trace_facts_from_a_trace_with_calls() -> None:
    assert TraceFacts is not None, "TraceFacts is required"
    path = "src/devops_cli/roadmap/agent_run.py"
    trace = RunTrace(
        tool_calls=[
            ToolCallRecord("read_file", json.dumps({"path": path})),
            ToolCallRecord("search_code", json.dumps({"pattern": "needle"})),
        ]
    )

    facts = TraceFacts.of(trace)

    assert facts.tools == frozenset({"read_file", "search_code"})
    assert facts.paths == frozenset({path})


def test_trace_facts_from_a_zero_call_trace() -> None:
    assert TraceFacts is not None, "TraceFacts is required"
    facts = TraceFacts.of(RunTrace())

    assert facts.tools == frozenset()
    assert facts.paths == frozenset()


_ANSWERS_SERIES = "devops_cli_ai_model_answers_total"


def _answered(model_name: str | None) -> ModelResponse:
    return ModelResponse(
        parts=[TextPart("ok")],
        usage=RequestUsage(input_tokens=10, output_tokens=2),
        model_name=model_name,
    )


def _answers(
    monkeypatch: pytest.MonkeyPatch, asked: str, replies: Sequence[ModelResponse]
) -> list[tuple[float, dict[str, str]]]:
    """The (value, labels) of each answer count that a run of `replies` to a model asked for
    `asked` emits."""
    emitted: list[tuple[float, dict[str, str]]] = []

    def record(instrument: Any, value: float, labels: dict[str, str] | None = None) -> None:
        if instrument.name == _ANSWERS_SERIES:
            emitted.append((value, labels or {}))

    monkeypatch.setattr("devops_cli.telemetry.instruments.emit", record)
    record_run_spend(
        FunctionModel(lambda m, i: _reply(1, 1), model_name=asked),
        [ModelRequest(parts=[UserPromptPart("go")]), *replies],
        0.5,
        stage="analysis",
    )
    return emitted


def test_a_fallback_answer_is_counted_with_the_model_that_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a slot that reads Sonnet while DeepSeek answers shows in the answer count (#4205)."""
    emitted = _answers(monkeypatch, "claude-sonnet-5-5", [_answered("deepseek-v4.1-flash-1017")])

    assert emitted == [
        (
            1,
            {
                "asked": "claude-sonnet-5-5",
                "answered": "deepseek-v4.1-flash-1017",
                "fallback": "true",
                "row": "other",
            },
        )
    ]


@pytest.mark.parametrize(
    ("asked", "answered"),
    [
        ("claude-sonnet-5-5", "claude-sonnet-5-5"),
        ("qwen3-coder:30b", "ollama_chat/qwen3-coder:30b"),
        ("hf.co/example/model-GGUF:Q4", "ollama_chat/hf.co/example/model-GGUF:Q4"),
    ],
    ids=["same", "provider-prefix", "provider-prefix-on-a-path"],
)
def test_the_asked_model_with_a_provider_prefix_is_no_fallback(
    monkeypatch: pytest.MonkeyPatch, asked: str, answered: str
) -> None:
    """Verify a reply that names the asked model under a provider prefix counts as no fallback."""
    emitted = _answers(monkeypatch, asked, [_answered(answered)])

    assert emitted == [
        (1, {"asked": asked, "answered": answered, "fallback": "false", "row": "other"})
    ]


def test_each_reply_of_a_run_is_counted_under_the_model_that_answered_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a run whose replies come from two models adds one count to each series."""
    emitted = _answers(
        monkeypatch,
        "claude-sonnet-5-5",
        [_answered("claude-sonnet-5-5"), _answered("deepseek-v4.1-flash-1017")],
    )

    assert sorted((labels["answered"], labels["fallback"], value) for value, labels in emitted) == [
        ("claude-sonnet-5-5", "false", 1),
        ("deepseek-v4.1-flash-1017", "true", 1),
    ]


def test_a_reply_that_names_no_model_adds_no_answer_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a reply with no model name adds no series, so nothing reads as a fallback."""
    assert _answers(monkeypatch, "claude-sonnet-5-5", [_answered(None)]) == []


def test_the_spend_record_keeps_the_model_that_answered(spend_ledger: SpendLedger) -> None:
    """Verify the record names the asked model in `model` and the answering model in
    `served_model`, so a slot cannot read Sonnet while DeepSeek answers (#4205)."""
    record_run_spend(
        FunctionModel(lambda m, i: _reply(1, 1), model_name="claude-sonnet-5-5"),
        [
            ModelRequest(parts=[UserPromptPart("go")]),
            _answered("deepseek-v4.1-flash-1017"),
        ],
        0.5,
        stage="analysis",
    )

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute("SELECT model, served_model FROM ai_spend_records").fetchall()
    assert rows == [("claude-sonnet-5-5", "deepseek-v4.1-flash-1017")]


_GATEWAY_URL = "https://llm.example.com/v1"


class _GatewayModel:
    """The three facts of a bridge model that `record_run_spend` reads: the name, the provider
    and the URL of the gateway that it sends to."""

    system = "openai"

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.served_by = _GATEWAY_URL


def _run_on_the_gateway(config: Callable[..., Any], asked: str, answered: str | None) -> None:
    """Record one run on `asked` when the gateway host is the cluster host and the reply names
    `answered`."""
    config(k8s={"domain": "example.com"}, ai={"gateway_url": _GATEWAY_URL})
    record_run_spend(
        _GatewayModel(asked),  # type: ignore[arg-type]
        [ModelRequest(parts=[UserPromptPart("go")]), _answered(answered)],
        0.5,
        stage="stage",
    )


def _spend_row(ledger: SpendLedger) -> tuple[Any, ...]:
    with contextlib.closing(sqlite3.connect(ledger.db_path)) as conn:
        row: tuple[Any, ...] = conn.execute(
            "SELECT served_model, pricing_source, cost_usd FROM ai_spend_records"
        ).fetchone()
    return row


@pytest.mark.parametrize(
    ("asked", "source"),
    [
        ("claude-sonnet-5-5", "genai_prices:anthropic"),
        ("claude-haiku-5-5", "genai_prices:anthropic"),
        ("gemini-3.8-flash", "genai_prices:google"),
    ],
)
def test_a_run_on_a_hosted_group_that_no_reply_names_is_priced_by_the_asked_model(
    spend_ledger: SpendLedger, config: Callable[..., Any], asked: str, source: str
) -> None:
    """Verify a hosted group behind a gateway that is the cluster host costs money when the
    replies name no model: the record is not local, and the asked model prices it (#3665)."""
    _run_on_the_gateway(config, asked, None)

    served_model, pricing_source, cost = _spend_row(spend_ledger)
    assert (served_model, pricing_source, cost > 0) == (asked, source, True)


def test_a_run_whose_reply_names_a_model_with_no_price_warns_and_is_not_local(
    spend_ledger: SpendLedger, config: Callable[..., Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Verify a reply that names a model which nothing prices is recorded as hosted at $0 with
    the source `unknown`, and that the warning names the model (#3665)."""
    unpriced = "example-provider/unpriced-model"

    with caplog.at_level(logging.WARNING, logger="devops_cli.ai.spend.pricing"):
        _run_on_the_gateway(config, "claude-sonnet-5-5", unpriced)

    assert (_spend_row(spend_ledger), [unpriced in r.getMessage() for r in caplog.records]) == (
        (unpriced, "unknown", 0.0),
        [True],
    )


def test_a_run_on_the_deepseek_group_costs_its_cached_and_new_input_and_its_output(
    spend_ledger: SpendLedger, config: Callable[..., Any], otlp: FakeCollector
) -> None:
    """Verify a run on the group that runs the Service adds its cost to the ledger and to
    `devops_cli_ai_spend_usd_total` under the route name (#4403). Of 1,000,000 prompt tokens,
    900,000 come from the cache of the provider: 0.1 x 0.0784 + 0.9 x 0.002352 + 0.1 x 0.2352
    USD for 100,000 completion tokens."""
    deepseek = "deepseek-v4.1-flash-1017"
    config(k8s={"domain": "example.com"}, ai={"gateway_url": _GATEWAY_URL})

    record_run_spend(
        _GatewayModel(deepseek),  # type: ignore[arg-type]
        [
            ModelRequest(parts=[UserPromptPart("go")]),
            ModelResponse(
                parts=[TextPart("ok")],
                usage=RequestUsage(
                    input_tokens=1_000_000, cache_read_tokens=900_000, output_tokens=100_000
                ),
                model_name=deepseek,
            ),
        ],
        0.5,
        stage="stage",
    )

    served_model, pricing_source, cost = _spend_row(spend_ledger)
    points = [(a["model"], round(v, 6)) for a, v in otlp.points("devops_cli_ai_spend_usd_total")]
    assert ((served_model, pricing_source, round(cost, 6)), points) == (
        (deepseek, "builtin:hosted_group_prices", 0.033477),
        [(deepseek, 0.033477)],
    )


def test_a_run_on_a_local_group_that_no_reply_names_stays_local(
    spend_ledger: SpendLedger, config: Callable[..., Any]
) -> None:
    """Verify a local group behind the cluster gateway keeps its local record at $0 (#3665)."""
    _run_on_the_gateway(config, "devops-coder", None)

    assert _spend_row(spend_ledger) == (None, "local", 0.0)


def test_a_reply_that_names_a_model_keeps_that_name_for_the_price(
    spend_ledger: SpendLedger, config: Callable[..., Any]
) -> None:
    """Verify the model that a reply names wins over the asked model: a run on Sonnet that
    DeepSeek answers is priced as DeepSeek (#3665)."""
    _run_on_the_gateway(config, "claude-sonnet-5-5", "deepseek-v4.1-flash-1017")

    served_model, pricing_source, _cost = _spend_row(spend_ledger)
    assert (served_model, pricing_source) == (
        "deepseek-v4.1-flash-1017",
        "builtin:hosted_group_prices",
    )
