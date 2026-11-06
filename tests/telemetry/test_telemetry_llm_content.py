"""Tests for keeping LLM prompt and reply text out of telemetry by default (#606)."""

from __future__ import annotations

import re
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import httpx2
import pytest
from opentelemetry.sdk.trace import SpanProcessor

from devops_cli.ai.agents.agent import PydanticAgent
from devops_cli.ai.client import LLMClient
from devops_cli.config.settings import AIConfig, Settings, TelemetryConfig
from devops_cli.core.validation import is_loopback_or_private_host
from devops_cli.security.sanitizer import PRIVATE_HOST_PATTERNS
from devops_cli.telemetry.logfire import LogfireBridge, reset_logfire_bridge
from devops_cli.telemetry.tracer import (
    clear_span_buffer,
    get_recent_spans,
    reset_tracer,
)
from tests.llm_stream_fakes import serve_llm
from tests.support.fakes.http import WebFake


@pytest.fixture(autouse=True)
def _clean_telemetry() -> Generator[None]:
    reset_tracer()
    reset_logfire_bridge()
    clear_span_buffer()
    yield
    reset_tracer()
    reset_logfire_bridge()
    clear_span_buffer()


def _serve_reply(web: WebFake, text: str) -> None:
    """Answer every chat completion with a reply of `text`, at the HTTP edge."""
    body = {
        "model": "gpt-4o",
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    serve_llm(web, lambda _request: httpx2.Response(200, json=body))


def test_private_host_patterns_defined_and_cross_checked_with_validation() -> None:
    """Verify PRIVATE_HOST_PATTERNS matches private/internal hosts and cross-checks with is_loopback_or_private_host."""
    assert isinstance(PRIVATE_HOST_PATTERNS, tuple)
    assert len(PRIVATE_HOST_PATTERNS) > 0

    combined_re = re.compile("|".join(PRIVATE_HOST_PATTERNS), re.IGNORECASE)

    test_hosts = [
        "node1.example.internal",
        "service.local",
        "router.lan",
        "workstation.corp",
        "nas.home.arpa",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.100",
        "127.0.0.1",
        "localhost",
    ]

    for host in test_hosts:
        match = combined_re.search(host)
        assert match is not None, f"Expected {host} to match PRIVATE_HOST_PATTERNS"
        assert is_loopback_or_private_host(host), (
            f"Expected {host} to be recognized as private by is_loopback_or_private_host"
        )

    code_identifiers = [
        "os.path",
        "json.dumps",
        "pydantic.BaseModel",
        "unified.dispatch",
        "span.set_attribute",
        "example.com",
    ]
    for identifier in code_identifiers:
        assert combined_re.search(identifier) is None, (
            f"Expected code identifier {identifier} NOT to match PRIVATE_HOST_PATTERNS"
        )


def test_telemetry_config_capture_llm_content_default_false() -> None:
    """Verify TelemetryConfig defaults capture_llm_content to False."""
    config = TelemetryConfig()
    assert hasattr(config, "capture_llm_content")
    assert config.capture_llm_content is False


def _dispatch_attributes(config: Any, capture: bool) -> dict[str, Any]:
    """The attributes of the one `ai.llm.dispatch` span of a chat with capture on or off."""
    config(telemetry={"enabled": True, "capture_llm_content": capture})
    clear_span_buffer()
    ai_cfg = AIConfig(provider="openai", model="gpt-4o", api_base_url="https://example.com/v1")
    client = LLMClient(ai_cfg, api_key="sk-test", cache_enabled=False)
    client.chat("system instruction", "user query containing node1.example.internal")

    spans = [s for s in get_recent_spans() if s.get("name") == "ai.llm.dispatch"]
    assert len(spans) == 1
    return {a["key"]: a["value"] for a in spans[0].get("attributes", [])}


def test_ai_llm_dispatch_spans_gate_prompt_and_response_preview(
    web: WebFake, config: Any, otlp: Any
) -> None:
    """Verify native ai.llm.dispatch spans omit preview attributes when capture is False, include when True."""
    _serve_reply(web, "stubbed response with sensitive details")

    off = _dispatch_attributes(config, capture=False)
    on = _dispatch_attributes(config, capture=True)

    assert ("llm.prompt_preview" in off, "llm.response_preview" in off) == (False, False)
    assert "node1.example.internal" in on["llm.prompt_preview"]["stringValue"]
    assert "stubbed response" in on["llm.response_preview"]["stringValue"]


def test_logfire_bridge_scrubbing_and_content_inclusion() -> None:
    """Verify LogfireBridge configures ScrubbingOptions with PRIVATE_HOST_PATTERNS and wires include_content."""
    import logfire

    bridge = LogfireBridge()

    # When capture_llm_content is False
    settings_false = Settings()
    settings_false.telemetry.capture_llm_content = False
    with (
        patch("logfire.configure") as mock_configure,
        patch("logfire.instrument_pydantic_ai") as mock_pydantic_ai,
    ):
        bridge.configure(settings=settings_false, token="token-test", send_to_logfire=True)
        mock_configure.assert_called_once()
        scrubbing = mock_configure.call_args.kwargs.get("scrubbing")
        assert isinstance(scrubbing, logfire.ScrubbingOptions)
        assert scrubbing.extra_patterns == PRIVATE_HOST_PATTERNS
        mock_pydantic_ai.assert_called_once_with(include_content=False)

    reset_logfire_bridge()
    bridge = LogfireBridge()

    # When capture_llm_content is True
    settings_true = Settings()
    settings_true.telemetry.capture_llm_content = True
    with (
        patch("logfire.configure") as mock_configure,
        patch("logfire.instrument_pydantic_ai") as mock_pydantic_ai,
    ):
        bridge.configure(settings=settings_true, token="token-test", send_to_logfire=True)
        mock_configure.assert_called_once()
        scrubbing = mock_configure.call_args.kwargs.get("scrubbing")
        assert isinstance(scrubbing, logfire.ScrubbingOptions)
        assert scrubbing.extra_patterns == PRIVATE_HOST_PATTERNS
        mock_pydantic_ai.assert_called_once_with(include_content=True)


def test_logfire_scrubber_redacts_private_hosts() -> None:
    """Verify Logfire scrubber with PRIVATE_HOST_PATTERNS redacts internal hostname."""
    import logfire._internal.scrubbing as s

    scrubber = s.Scrubber(patterns=PRIVATE_HOST_PATTERNS)
    scrubbed, notes = scrubber.scrub_value(
        ("attributes", "host"), "Connect to node1.example.internal now"
    )
    assert "[Scrubbed" in scrubbed
    assert len(notes) == 1
    assert notes[0]["matched_substring"] == "node1.example.internal"


class _CapturingSpanProcessor(SpanProcessor):
    def __init__(self, target_list: list[Any]) -> None:
        self.target_list = target_list

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        pass

    def on_end(self, span: Any) -> None:
        self.target_list.append(span)

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _assert_no_host_in_recent_spans(host: str) -> None:
    for span in get_recent_spans():
        for attr in span.get("attributes", []):
            str_val = str(attr.get("value", {}).get("stringValue", ""))
            assert host not in str_val, f"{host} leaked into tracer span {span.get('name')}: {attr}"


def _assert_no_host_in_logfire_spans(host: str, spans: list[Any]) -> None:
    for lf_span in spans:
        lf_attrs = getattr(lf_span, "attributes", {}) or {}
        for k, v in lf_attrs.items():
            assert host not in str(v), f"{host} leaked into Logfire span attribute {k}: {v}"


def _has_prompt_preview_host(host: str) -> bool:
    for span in get_recent_spans():
        for attr in span.get("attributes", []):
            if attr.get("key") == "llm.prompt_preview":
                val = str(attr.get("value", {}).get("stringValue", ""))
                if host in val:
                    return True
    return False


def test_pydantic_agent_keeps_private_host_out_of_telemetry_when_capture_off(
    web: WebFake, config: Any, otlp: Any
) -> None:
    """Drive PydanticAgent + LLMClient and assert hostname is in no Logfire or tracer attribute."""
    captured_logfire_spans: list[Any] = []
    _serve_reply(web, "reply from stubbed agent")
    ai_cfg = AIConfig(provider="openai", model="gpt-4o", api_base_url="https://example.com/v1")

    config(telemetry={"enabled": True, "capture_llm_content": False})
    clear_span_buffer()
    import logfire

    logfire.configure(
        send_to_logfire=False,
        additional_span_processors=[_CapturingSpanProcessor(captured_logfire_spans)],
        scrubbing=logfire.ScrubbingOptions(extra_patterns=PRIVATE_HOST_PATTERNS),
    )

    client = LLMClient(ai_cfg, api_key="sk-test", cache_enabled=False)
    agent: PydanticAgent[Any, Any] = PydanticAgent(client=client, name="TestSecurityAgent")

    res = agent.run("Connect to node1.example.internal and check status")
    assert res.content == "reply from stubbed agent"

    _assert_no_host_in_recent_spans("node1.example.internal")
    _assert_no_host_in_logfire_spans("node1.example.internal", captured_logfire_spans)


def test_pydantic_agent_records_prompt_preview_when_capture_on(
    web: WebFake, config: Any, otlp: Any
) -> None:
    """Assert prompt preview returns when capture_llm_content is True."""
    _serve_reply(web, "reply from stubbed agent")
    ai_cfg = AIConfig(provider="openai", model="gpt-4o", api_base_url="https://example.com/v1")

    config(telemetry={"enabled": True, "capture_llm_content": True})
    clear_span_buffer()

    client = LLMClient(ai_cfg, api_key="sk-test", cache_enabled=False)
    agent: PydanticAgent[Any, Any] = PydanticAgent(client=client, name="TestSecurityAgent")

    agent.run("Connect to node1.example.internal and check status")

    assert _has_prompt_preview_host("node1.example.internal"), (
        "Expected node1.example.internal in prompt preview when capture is on"
    )
