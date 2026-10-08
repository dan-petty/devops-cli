"""Unit tests for LLM structured output, schema repair, and error reflection retry engine.

The request-body and cache cases answer at the HTTP edge with httpx2's `MockTransport`, read and
write the per-test response cache the autouse fixture provides, and retry with no backoff.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx2
import pytest
from pydantic import BaseModel, Field

from devops_cli.ai.client.models import (
    AIClientError,
    LLMResponse,
    StructuredOutputValidationError,
)
from devops_cli.ai.client.structured import (
    StructuredOutputMixin,
    _build_reflection_message,
    _extract_candidate_json,
    _parse_json_payload,
    _prepare_structured_messages,
    _repair_and_validate_payload,
    _validate_schema_payload,
)
from devops_cli.ai.client.unified import LLMClient
from devops_cli.ai.schema_reflection import SchemaReflectionReport
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from devops_cli.roadmap.refine import RefinementProposal
from devops_cli.telemetry.tracer import get_tracer
from tests.llm_stream_fakes import route_client


class DemoReport(BaseModel):
    """Test schema for structured generation."""

    title: str
    severity: str = "medium"
    score: int = Field(ge=0, le=100)
    tags: list[str] = Field(default_factory=list)


def _create_mock_client() -> LLMClient:
    """Helper to instantiate LLMClient with safe test configuration."""
    cfg = AIConfig(
        provider="ollama",
        model="demo-model",
        ollama_base_url="http://example.com:11434",
        max_retries=2,
    )
    return LLMClient(config=cfg, api_key="dummy-key")


def test_build_reflection_message() -> None:
    """Verify reflection message formatting and bounded role definition."""
    msg = _build_reflection_message("Field required: score")
    assert (msg.role, "Field required: score" in msg.content) == ("user", True)


def test_repair_and_validate_payload() -> None:
    """Verify end-to-end extraction, repair, and schema validation."""
    raw = "<think>notes</think>\n```json\n{'title': 'RepairMe', 'score': 50}\n```"
    model, was_repaired, err = _repair_and_validate_payload(raw, DemoReport)
    assert (model is not None, was_repaired, err) == (True, True, None)
    if model is not None:
        assert (model.title, model.score) == ("RepairMe", 50)


def test_llm_client_inherits_structured_mixin() -> None:
    """Verify LLMClient class is an instance of StructuredOutputMixin."""
    client = _create_mock_client()
    assert isinstance(client, StructuredOutputMixin)


def test_extract_candidate_json_handles_fences_and_thinking() -> None:
    """Verify thinking tags and markdown code blocks are cleanly stripped."""
    raw = (
        "<think>Examining the AST context</think>\n"
        "```json\n"
        '{"title": "BufferOverflow", "severity": "high", "score": 90}\n'
        "```"
    )
    candidate = _extract_candidate_json(raw)
    assert candidate == '{"title": "BufferOverflow", "severity": "high", "score": 90}'


def test_parse_json_payload_clean_and_repair() -> None:
    """Verify clean JSON passes directly and malformed JSON triggers json_repair."""
    clean_raw = '{"title": "Safe", "score": 10}'
    data_clean, repaired_clean, err_clean = _parse_json_payload(clean_raw, clean_raw)
    assert (repaired_clean, err_clean, data_clean["score"]) == (False, None, 10)

    malformed_raw = "{'title': 'Repaired', 'score': 20, }"
    data_rep, repaired_rep, err_rep = _parse_json_payload(malformed_raw, malformed_raw)
    assert (repaired_rep, err_rep, data_rep["title"], data_rep["score"]) == (
        True,
        None,
        "Repaired",
        20,
    )

    invalid_raw = "This is pure freeform text with no JSON."
    data_inv, repaired_inv, err_inv = _parse_json_payload(invalid_raw, invalid_raw)
    assert (data_inv, repaired_inv, err_inv is not None) == (None, False, True)


def test_validate_schema_payload_reports_every_violation() -> None:
    """Verify valid payloads produce models and an invalid one a report holding every violation."""
    valid_data = {"title": "Valid", "severity": "low", "score": 42, "tags": ["test"]}
    model, err = _validate_schema_payload(valid_data, DemoReport)
    assert (err, model is not None) == (None, True)
    if model is not None:
        assert (model.title, model.score, model.severity) == ("Valid", 42, "low")

    invalid_data = {"title": "MissingScore"}
    model_inv, err_inv = _validate_schema_payload(invalid_data, DemoReport)
    assert isinstance(err_inv, SchemaReflectionReport)
    assert (model_inv, err_inv.total_errors, len(err_inv.violations), err_inv.remaining_count) == (
        None,
        1,
        1,
        0,
    )


def test_prepare_structured_messages_variants() -> None:
    """Verify prompt and user arguments normalize cleanly to ChatMessage list."""
    msgs_from_prompt = _prepare_structured_messages("Audit report request", None)
    assert (len(msgs_from_prompt), msgs_from_prompt[0].role, msgs_from_prompt[0].content) == (
        1,
        "user",
        "Audit report request",
    )

    msgs_from_user = _prepare_structured_messages(None, "User param request")
    assert (len(msgs_from_user), msgs_from_user[0].content) == (1, "User param request")

    existing_msgs = [
        ChatMessage(role="system", content="init"),
        ChatMessage(role="user", content="req"),
    ]
    msgs_from_list = _prepare_structured_messages(existing_msgs, None)
    assert len(msgs_from_list) == 2

    with pytest.raises(ValueError, match="Either prompt or user text must be provided"):
        _prepare_structured_messages(None, None)


def test_chat_structured_immediate_success() -> None:
    """Verify chat_structured succeeds on first attempt with clean JSON."""
    client = _create_mock_client()
    raw_response = '{"title": "ZeroBug", "severity": "low", "score": 100, "tags": ["sec"]}'

    with patch.object(client, "chat_messages", return_value=LLMResponse(raw_response)) as mock_chat:
        report = client.chat_structured(
            system="You are a reviewer",
            prompt="Generate a report",
            schema=DemoReport,
        )
        assert (mock_chat.call_count, report.title, report.score) == (1, "ZeroBug", 100)


def test_chat_structured_local_repair_no_network_retry() -> None:
    """Verify malformed JSON is repaired locally without consuming extra retry turns."""
    client = _create_mock_client()
    malformed_response = (
        "```json\n{\n  'title': 'RepairedBug',\n  'severity': 'high',\n  'score': 75,\n}\n```"
    )

    with patch.object(
        client, "chat_messages", return_value=LLMResponse(malformed_response)
    ) as mock_chat:
        report = client.chat_structured(
            system="You are a reviewer",
            prompt="Generate a report",
            schema=DemoReport,
        )
        assert (mock_chat.call_count, report.title, report.score, report.severity) == (
            1,
            "RepairedBug",
            75,
            "high",
        )


def test_chat_structured_reflection_retry_succeeds_on_second_turn() -> None:
    """Verify validation error triggers reflection prompt and recovers on retry."""
    client = _create_mock_client()
    bad_attempt_1 = '{"title": "MissingRequiredScore"}'
    good_attempt_2 = '{"title": "FixedReport", "severity": "high", "score": 88}'

    with patch.object(
        client,
        "chat_messages",
        side_effect=[LLMResponse(bad_attempt_1), LLMResponse(good_attempt_2)],
    ) as mock_chat:
        report = client.chat_structured(
            system="System prompt",
            prompt="Initial request",
            schema=DemoReport,
            backoff_seconds=0.01,
        )
        assert (mock_chat.call_count, report.title, report.score) == (2, "FixedReport", 88)
        second_call_messages = mock_chat.call_args_list[1][0][1]
        assert len(second_call_messages) == 3
        assert (
            second_call_messages[0].role,
            second_call_messages[1].role,
            second_call_messages[2].role,
        ) == ("user", "assistant", "user")
        assert "Field: `score`" in second_call_messages[2].content


def test_chat_structured_retry_exhaustion_raises_client_error() -> None:
    """Verify retry exhaustion after max_retries raises AIClientError with actionable context."""
    client = _create_mock_client()
    bad_payload = "Non-parseable unstructured output"

    with patch.object(
        client,
        "chat_messages",
        side_effect=[
            LLMResponse(bad_payload),
            LLMResponse(bad_payload),
            LLMResponse(bad_payload),
        ],
    ) as mock_chat:
        with pytest.raises(
            AIClientError,
            match="Response validation failed for model 'demo-model' after 3 attempts",
        ):
            client.chat_structured(
                system="System prompt",
                prompt="Initial prompt",
                schema=DemoReport,
                max_retries=2,
                backoff_seconds=0.01,
            )
        assert mock_chat.call_count == 3


def test_chat_structured_requires_schema() -> None:
    """Verify ValueError is raised if schema is omitted."""
    client = _create_mock_client()
    with pytest.raises(ValueError, match="A schema model class must be provided"):
        client.chat_structured(system="sys", prompt="req", schema=None)


# ── The schema request and the response cache, at the HTTP edge (#1363) ──────────────────────

_SYSTEM = "You refine one issue."
_PROMPT = '{"number": 12}'
_VALID = json.dumps(
    {
        "problem_statement": "Refine writes nothing.",
        "acceptance_criteria": [{"description": "A section is written.", "verification": "pytest"}],
    }
)
_MARKDOWN = (
    "# RefinementProposal - Issue #12\n\n| Field | Value |\n|---|---|\n| problem | stale |\n"
)
# Three violations: a criterion given as a string, and two keys the schema does not define.
_THREE_VIOLATIONS = json.dumps(
    {"problem_statement": "x", "acceptance_criteria": ["A string"], "issue": 12, "title": "t"}
)
_CONFIGS = {
    "gateway": AIConfig(
        provider="gateway", model="demo-model", gateway_url="http://example.com:4000/v1"
    ),
    "openai": AIConfig(
        provider="openai", model="demo-model", api_base_url="http://example.com:8080/v1"
    ),
    "ollama": AIConfig(
        provider="ollama", model="demo-model", ollama_urls=["http://example.com:11434"]
    ),
}


def _structured_client(provider: str = "gateway") -> LLMClient:
    return LLMClient(_CONFIGS[provider].model_copy(), api_key="sk")


def _reply(provider: str, text: str) -> httpx2.Response:
    """A provider's non-streamed chat reply carrying `text`, with its token counts."""
    if provider == "ollama":
        message = {"role": "assistant", "content": text}
        counts = {"prompt_eval_count": 1, "eval_count": 1}
        return httpx2.Response(200, json={"message": message, "done": True, **counts})
    choice = {"message": {"content": text}, "finish_reason": "stop"}
    usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
    return httpx2.Response(200, json={"choices": [choice], "usage": usage})


def _answering(provider: str, *texts: str) -> Any:
    """A transport handler answering with each text in turn, then the last one again."""
    replies = list(texts)

    def answer(_request: httpx2.Request) -> httpx2.Response:
        return _reply(provider, replies.pop(0) if len(replies) > 1 else replies[0])

    return answer


def _sent_system() -> str:
    """The system message chat_structured sends for RefinementProposal."""
    schema = json.dumps(RefinementProposal.model_json_schema(), ensure_ascii=False)
    return "\n\n".join((_SYSTEM, load_task_prompt("structured_output_schema.md"), schema))


def _cached_texts(tmp_path: Path) -> list[str]:
    """The reply each entry the per-test response cache wrote to disk holds."""
    files = (tmp_path / "test_llm_cache").rglob("*.json")
    return [json.loads(path.read_text(encoding="utf-8"))["content"] for path in files]


def test_each_provider_is_sent_the_schema_and_only_its_own_constraint(
    monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> None:
    """Verify the schema ends the system message for every provider, the gateway alone gets
    response_format without strict, ollama alone gets format, and openai gets neither."""
    bodies: dict[str, Any] = {}
    for provider in _CONFIGS:
        client = _structured_client(provider)
        sent = route_client(client, monkeypatch, _answering(provider, _VALID))
        client.chat_structured(_SYSTEM, _PROMPT, RefinementProposal, use_cache=False)
        bodies[provider] = json.loads(sent[0].content)

    schema = RefinementProposal.model_json_schema()
    messages = [{"role": "system", "content": _sent_system()}, {"role": "user", "content": _PROMPT}]
    compat = {"model": "demo-model", "messages": messages, "temperature": 0.1, "top_p": 0.95}
    assert bodies == {
        "gateway": compat
        | {
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "RefinementProposal", "schema": schema},
            }
        },
        "openai": compat,
        "ollama": {
            "model": "demo-model",
            "stream": False,
            "messages": messages,
            "think": False,
            "options": {"temperature": 0.1, "top_p": 0.95, "num_ctx": 32768},
            "format": schema,
        },
    }


def test_a_reply_that_fails_the_schema_gets_the_reflection_and_is_never_cached(
    monkeypatch: pytest.MonkeyPatch, public_dns: str, tmp_path: Path
) -> None:
    """Verify a Markdown first reply is answered with the reflection and never cached."""
    client = _structured_client()
    sent = route_client(client, monkeypatch, _answering("gateway", _MARKDOWN, _VALID))

    proposal = client.chat_structured(_SYSTEM, _PROMPT, RefinementProposal, backoff_seconds=0)

    retry = json.loads(sent[1].content)["messages"]
    assert (
        proposal,
        len(sent),
        [message["role"] for message in retry],
        retry[2]["content"],
        "Validation Error" in retry[3]["content"],
        [text for text in _cached_texts(tmp_path) if text == _MARKDOWN],
    ) == (
        RefinementProposal.model_validate_json(_VALID),
        2,
        ["system", "user", "assistant", "user"],
        _MARKDOWN,
        True,
        [],
    )


def test_a_cached_reply_that_fails_the_schema_is_never_served(
    monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> None:
    """Verify a Markdown reply cached at the first attempt's key is passed over for the
    transport, whose valid reply then takes its place."""
    client = _structured_client()
    key = client.cache.generate_key(
        "gateway",
        "demo-model",
        _sent_system(),
        [ChatMessage(role="user", content=_PROMPT)],
        {"enable_thinking": False},
    )
    client.cache.set(
        key=key,
        provider="gateway",
        model="demo-model",
        system=_sent_system(),
        prompt=_PROMPT,
        content=_MARKDOWN,
    )
    sent = route_client(client, monkeypatch, _answering("gateway", _VALID))

    proposal = client.chat_structured(_SYSTEM, _PROMPT, RefinementProposal, backoff_seconds=0)

    cached = client.cache.get(key)
    assert (
        proposal,
        [
            [message["role"] for message in json.loads(request.content)["messages"]]
            for request in sent
        ],
        cached.content if cached else None,
    ) == (RefinementProposal.model_validate_json(_VALID), [["system", "user"]], _VALID)


def test_a_valid_first_reply_is_cached_and_served(
    monkeypatch: pytest.MonkeyPatch, public_dns: str, tmp_path: Path
) -> None:
    """Verify a valid first reply is written to the cache and answers the same call again."""
    client = _structured_client()
    sent = route_client(client, monkeypatch, _answering("gateway", _VALID))

    first = client.chat_structured(_SYSTEM, _PROMPT, RefinementProposal)
    again = client.chat_structured(_SYSTEM, _PROMPT, RefinementProposal)

    assert (first, again, len(sent), _cached_texts(tmp_path)) == (
        RefinementProposal.model_validate_json(_VALID),
        RefinementProposal.model_validate_json(_VALID),
        1,
        [_VALID],
    )


@pytest.mark.parametrize(("reply", "violations"), [(_THREE_VIOLATIONS, 3), (_MARKDOWN, 0)])
def test_the_validation_error_counts_the_last_replys_schema_violations(
    monkeypatch: pytest.MonkeyPatch, public_dns: str, reply: str, violations: int
) -> None:
    """Verify the error carries the last reply's violation count, 0 when it held no JSON."""
    client = _structured_client()
    sent = route_client(client, monkeypatch, _answering("gateway", reply))

    with pytest.raises(StructuredOutputValidationError) as raised:
        client.chat_structured(_SYSTEM, _PROMPT, RefinementProposal, backoff_seconds=0)

    assert (raised.value.violations, len(sent)) == (violations, 3)


# Seven violations, two more than a capped report would keep: two criteria given as strings and
# five keys the schema does not define.
_SEVEN_VIOLATIONS = json.dumps(
    {
        "problem_statement": "x",
        "acceptance_criteria": ["first", "second"],
        **{f"invented_{index}": index for index in range(1, 6)},
    }
)
# Two violations, one of them a key whose name is the model's own text.
_INVENTED_KEY = json.dumps(
    {"problem_statement": "x", "acceptance_criteria": ["a string"], "leaked_model_key": "y"}
)


def test_the_retry_prompt_names_every_violation_of_the_last_reply(
    monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> None:
    """Verify the reflection sent with the retry is the schema report's prescriptive prompt and
    names every violation's field path, not only the first five."""
    client = _structured_client()
    sent = route_client(client, monkeypatch, _answering("gateway", _SEVEN_VIOLATIONS, _VALID))

    client.chat_structured(_SYSTEM, _PROMPT, RefinementProposal, backoff_seconds=0)

    reflection = json.loads(sent[1].content)["messages"][-1]["content"]
    paths = [
        "acceptance_criteria[0]",
        "acceptance_criteria[1]",
        *(f"invented_{index}" for index in range(1, 6)),
    ]
    assert (
        "Found 7 schema violation(s):" in reflection,
        [path for path in paths if f"Field: `{path}`" not in reflection],
    ) == (True, [])


def test_the_validation_error_holds_no_key_the_model_invented(
    monkeypatch: pytest.MonkeyPatch, public_dns: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify the error's message carries the violation count and error types alone, so a key
    the model invented reaches neither the message nor the chat_structured span nor a log."""
    exported: list[dict[str, Any]] = []
    monkeypatch.setattr(
        get_tracer(), "_send_payload", lambda _path, payload: exported.append(payload)
    )
    client = _structured_client()
    route_client(client, monkeypatch, _answering("gateway", _INVENTED_KEY))

    with (
        caplog.at_level(logging.DEBUG),
        pytest.raises(StructuredOutputValidationError) as raised,
    ):
        client.chat_structured(_SYSTEM, _PROMPT, RefinementProposal, backoff_seconds=0)

    spans = [
        span
        for payload in exported
        for resource in payload.get("resourceSpans", [])
        for scope in resource["scopeSpans"]
        for span in scope["spans"]
        if span["name"] == "ai.client.chat_structured"
    ]
    assert (
        str(raised.value),
        len(spans),
        "leaked_model_key" in json.dumps(spans),
        "leaked_model_key" in caplog.text,
    ) == (
        "Response validation failed for model 'demo-model' after 3 attempts: the last reply had "
        "2 schema violation(s) (extra_forbidden, model_type).",
        1,
        False,
        False,
    )
