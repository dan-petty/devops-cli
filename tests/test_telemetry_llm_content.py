"""Tests for keeping LLM prompt and reply text out of telemetry by default (#606)."""

from __future__ import annotations

import re
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import SpanProcessor

from devops_cli.ai.agents.agent import PydanticAgent
from devops_cli.ai.client import LLMClient, LLMResponse
from devops_cli.config.settings import AIConfig, Settings, TelemetryConfig
from devops_cli.core.validation import is_loopback_or_private_host
from devops_cli.models.ai import ChatMessage
from devops_cli.security.sanitizer import PRIVATE_HOST_PATTERNS
from devops_cli.telemetry.logfire import LogfireBridge, reset_logfire_bridge
from devops_cli.telemetry.tracer import (
    OTelTelemetryClient,
    clear_span_buffer,
    get_recent_spans,
    reset_tracer,
)


@pytest.fixture(autouse=True)
def _clean_telemetry(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setattr(OTelTelemetryClient, "_send_payload", lambda self, path, p: None)
    monkeypatch.setattr(OTelTelemetryClient, "_send_payload_sync", lambda self, path, p: None)
    reset_tracer()
    reset_logfire_bridge()
    clear_span_buffer()
    yield
    reset_tracer()
    reset_logfire_bridge()
    clear_span_buffer()


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


def test_ai_llm_dispatch_spans_gate_prompt_and_response_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify native ai.llm.dispatch spans omit preview attributes when capture is False, include when True."""

    def stubbed_driver(
        self: LLMClient, system: str, messages: list[ChatMessage], **_: Any
    ) -> LLMResponse:
        return LLMResponse(
            "stubbed response with sensitive details",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )

    monkeypatch.setattr(LLMClient, "_openai_compat_messages", stubbed_driver)
    ai_cfg = AIConfig(provider="openai", model="gpt-4o", api_base_url="https://example.com/v1")

    # Case 1: capture_llm_content is False (default)
    settings_false = Settings()
    settings_false.telemetry.capture_llm_content = False
    with patch(
        "devops_cli.telemetry.tracer._resolve_telemetry_settings",
        return_value=settings_false.telemetry,
    ):
        reset_tracer()
        clear_span_buffer()
        client = LLMClient(ai_cfg, api_key="sk-test", cache_enabled=False)
        client.chat("system instruction", "user query containing node1.example.internal")

        spans = [s for s in get_recent_spans() if s.get("name") == "ai.llm.dispatch"]
        assert len(spans) == 1
        attrs = {a["key"]: a["value"] for a in spans[0].get("attributes", [])}
        assert "llm.prompt_preview" not in attrs
        assert "llm.response_preview" not in attrs

    # Case 2: capture_llm_content is True
    settings_true = Settings()
    settings_true.telemetry.capture_llm_content = True
    with patch(
        "devops_cli.telemetry.tracer._resolve_telemetry_settings",
        return_value=settings_true.telemetry,
    ):
        reset_tracer()
        clear_span_buffer()
        client = LLMClient(ai_cfg, api_key="sk-test", cache_enabled=False)
        client.chat("system instruction", "user query containing node1.example.internal")

        spans = [s for s in get_recent_spans() if s.get("name") == "ai.llm.dispatch"]
        assert len(spans) == 1
        attrs = {a["key"]: a["value"] for a in spans[0].get("attributes", [])}
        assert "llm.prompt_preview" in attrs
        assert "node1.example.internal" in attrs["llm.prompt_preview"]["stringValue"]
        assert "llm.response_preview" in attrs
        assert "stubbed response" in attrs["llm.response_preview"]["stringValue"]


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drive PydanticAgent + LLMClient and assert hostname is in no Logfire or tracer attribute."""
    captured_logfire_spans: list[Any] = []

    def stubbed_driver(
        self: LLMClient, system: str, messages: list[ChatMessage], **_: Any
    ) -> LLMResponse:
        return LLMResponse(
            "reply from stubbed agent", prompt_tokens=20, completion_tokens=10, total_tokens=30
        )

    monkeypatch.setattr(LLMClient, "_openai_compat_messages", stubbed_driver)
    ai_cfg = AIConfig(provider="openai", model="gpt-4o", api_base_url="https://example.com/v1")

    settings_off = Settings()
    settings_off.telemetry.capture_llm_content = False

    with patch(
        "devops_cli.telemetry.tracer._resolve_telemetry_settings",
        return_value=settings_off.telemetry,
    ):
        reset_tracer()
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assert prompt preview returns when capture_llm_content is True."""

    def stubbed_driver(
        self: LLMClient, system: str, messages: list[ChatMessage], **_: Any
    ) -> LLMResponse:
        return LLMResponse(
            "reply from stubbed agent", prompt_tokens=20, completion_tokens=10, total_tokens=30
        )

    monkeypatch.setattr(LLMClient, "_openai_compat_messages", stubbed_driver)
    ai_cfg = AIConfig(provider="openai", model="gpt-4o", api_base_url="https://example.com/v1")

    settings_on = Settings()
    settings_on.telemetry.capture_llm_content = True

    with patch(
        "devops_cli.telemetry.tracer._resolve_telemetry_settings",
        return_value=settings_on.telemetry,
    ):
        reset_tracer()
        clear_span_buffer()

        client = LLMClient(ai_cfg, api_key="sk-test", cache_enabled=False)
        agent: PydanticAgent[Any, Any] = PydanticAgent(client=client, name="TestSecurityAgent")

        agent.run("Connect to node1.example.internal and check status")

        assert _has_prompt_preview_host("node1.example.internal"), (
            "Expected node1.example.internal in prompt preview when capture is on"
        )
