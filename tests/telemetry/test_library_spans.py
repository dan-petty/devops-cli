"""Library spans: the OpenTelemetry API spans of pydantic-ai and the gateway client reach the OTLP
fake through the exporter of the process's tracer, in the trace of the span open at the call."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx2
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.usage import RequestUsage

from devops_cli.ai.client.factory import build_agent
from devops_cli.ai.providers import create_pydantic_ai_provider
from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model
from devops_cli.dry_run.state import mark_dry_run_invocation
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import async_http_client
from devops_cli.telemetry.logfire import get_logfire_bridge
from devops_cli.telemetry.tracer import trace_span
from tests.support.fakes.http import WebFake
from tests.support.fakes.otlp import ExportedSpan, FakeCollector
from tests.support.llm_stream_fakes import serve_llm

PROMPT = "Plan item 4242 with the secret phrase violet-harbor"
TOOL_REPLY = "item 4242 has the label crimson-anchor"
GATEWAY = "https://example.com/v1"


def _lookup_item(item: int) -> str:
    """Read one item."""
    with trace_span("roadmap.lookup", attributes={"item": item}):
        return TOOL_REPLY


def _call_the_tool_then_answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    usage = RequestUsage(input_tokens=1200, output_tokens=40, cache_read_tokens=1000)
    if len(messages) == 1:
        return ModelResponse(
            parts=[ToolCallPart("_lookup_item", {"item": 4242}, tool_call_id="call-1")],
            usage=usage,
        )
    return ModelResponse(parts=[TextPart("planned")], usage=usage)


def _run_stage_agent() -> None:
    """Run an agent that calls one tool, in a row span, as a stage run does."""
    model = resolve_pydantic_ai_model(FunctionModel(_call_the_tool_then_answer))
    agent = build_agent(model, tools=[_lookup_item], name="stage")
    with trace_span("service.job"):
        agent.run_sync(PROMPT)


def _by_name(spans: list[ExportedSpan]) -> dict[str, ExportedSpan]:
    return {span.name.split(" ")[0]: span for span in spans}


def test_agent_spans_nest_under_the_row_span_with_token_usage(otlp: FakeCollector) -> None:
    """Verify an agent run in a row span exports its agent, model and tool spans under that span."""
    _run_stage_agent()

    spans = _by_name(otlp.spans)
    row, agent = spans["service.job"], spans["invoke_agent"]
    chats = [span for span in otlp.spans if span.name.startswith("chat ")]
    tool = spans["execute_tool"]
    assert {span.trace_id for span in otlp.spans} == {row.trace_id}
    assert agent.parent_span_id == row.span_id
    assert {chat.parent_span_id for chat in chats} == {agent.span_id}
    assert tool.parent_span_id == agent.span_id
    assert spans["roadmap.lookup"].parent_span_id == tool.span_id
    assert [
        (
            chat.attributes["gen_ai.usage.input_tokens"],
            chat.attributes["gen_ai.usage.output_tokens"],
            chat.attributes["gen_ai.usage.cache_read.input_tokens"],
        )
        for chat in chats
    ] == [("1200", "40", "1000"), ("1200", "40", "1000")]


def test_agent_spans_hold_no_prompt_or_tool_text_by_default(otlp: FakeCollector) -> None:
    """Verify the agent spans keep no prompt, tool argument or tool reply text by default."""
    _run_stage_agent()

    exported = json.dumps([span.attributes for span in otlp.spans])
    assert ("violet-harbor" in exported, "crimson-anchor" in exported) == (False, False)


def test_a_dry_run_exports_no_agent_span(otlp: FakeCollector) -> None:
    """Verify an agent run in a dry run sends no export request to the collector."""
    mark_dry_run_invocation(True)

    _run_stage_agent()

    assert otlp.spans == []


def test_agent_spans_reach_the_collector_with_the_logfire_bridge_on(otlp: FakeCollector) -> None:
    """Verify the agent spans of a run with the Logfire bridge on also reach the collector."""
    bridge = get_logfire_bridge()
    bridge.configure(token="unused", send_to_logfire=False)

    _run_stage_agent()
    bridge.flush()

    spans = _by_name(otlp.spans)
    assert spans["invoke_agent"].parent_span_id == spans["service.job"].span_id


def _chat_completion(_request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 1,
            "model": "deepseek-v4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "done"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        },
    )


async def _call_the_gateway_and_another_host() -> None:
    provider: Any = create_pydantic_ai_provider(
        "openai", base_url=GATEWAY, api_key="sk-test", gateway_caller=True
    )
    agent = Agent(OpenAIChatModel("deepseek-v4", provider=provider))
    with trace_span("service.job"):
        await agent.run("hello")
        async with async_http_client(EgressLevel.PUBLIC) as client:
            await client.get("https://example.com/other")


def test_trace_context_goes_to_the_gateway_and_no_other_host(
    otlp: FakeCollector, web: WebFake
) -> None:
    """Verify the gateway request carries the trace context and a request to another host none."""
    serve_llm(web, _chat_completion)

    asyncio.run(_call_the_gateway_and_another_host())

    sent = {request.url.split("?")[0]: request.headers for request in web.recorded}
    gateway = sent[f"{GATEWAY}/chat/completions"]
    http_span = _by_name(otlp.spans)["POST"]
    assert gateway["traceparent"] == f"00-{http_span.trace_id}-{http_span.span_id}-01"
    assert "traceparent" not in sent["https://example.com/other"]
