"""Library spans: the OpenTelemetry API spans of pydantic-ai, the MCP client and the gateway client.

devops-cli makes its own spans in `tracer.py`. A library makes its spans through the OpenTelemetry
API, which records nothing until the process sets an SDK tracer provider. `install_library_spans`
sets one, once for each process, when the process builds its first pydantic-ai model: a command
that builds no model loads no SDK (#858).

The provider exports through `SeamSpanExporter`. It encodes the spans with the official OTLP
encoder and gives the protobuf body to the exporter of the process's tracer
(`telemetry/exporter.py`, #1319), so library spans take the egress-checked client, go to the
collector that the own spans go to, and go nowhere in a dry run (#412). The stock OTLP exporters,
which `OTEL_EXPORTER_OTLP_ENDPOINT` turns on in Logfire, bypass all three.

The own spans put their ids in the API context (`tracer.py`), so a model or tool span nests under
the own span that was open when the agent ran, and an own span in a tool nests under the tool span.

- pydantic-ai: `Agent.instrument_all`, so every agent of the process makes `invoke_agent`, `chat`
  and `execute_tool` spans with their token use. Prompt, reply and tool text follow
  `telemetry.capture_llm_content`, off by default (#606). No binary content, no model request
  parameters and no metrics.
- MCP: fastmcp and the MCP SDK make their spans through the global provider.
- httpx: `instrument_gateway_client` instruments the LLM gateway's client only, so trace context
  and baggage go to the gateway and to no other host.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult

from devops_cli.config.defaults import DEFAULT_OTEL_DRAIN_TIMEOUT_SECONDS
from devops_cli.dry_run.state import in_dry_run_invocation
from devops_cli.telemetry.exporter import PROTOBUF_CONTENT_TYPE, OtlpSignal
from devops_cli.telemetry.tracer import get_tracer

if TYPE_CHECKING:
    import httpx2

_LOCK = threading.Lock()
# The provider of the process. Each export goes to the tracer of that time.
_PROVIDER: TracerProvider | None = None
# Whether pydantic-ai agents make spans now. A reset turns them off, not the provider.
_AGENTS_INSTRUMENTED = False


class SeamSpanExporter(SpanExporter):
    """An SDK span exporter that sends each batch through the exporter of the process's tracer."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        tracer = get_tracer()
        if not spans or not tracer.enabled or in_dry_run_invocation():
            return SpanExportResult.SUCCESS
        body = encode_spans(spans).SerializeToString()
        if tracer.export_encoded(OtlpSignal.TRACES, body, PROTOBUF_CONTENT_TYPE):
            return SpanExportResult.SUCCESS
        return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _library_resource() -> Resource:
    """The resource of the own spans, with the SDK's `telemetry.sdk.*` attributes in place of the
    tracer's."""
    own = get_tracer().resource_attributes()
    return Resource.create(
        {key: value for key, value in own.items() if not key.startswith("telemetry.sdk.")}
    )


def _provider() -> TracerProvider:
    """The provider of the process, made and set as the global provider on the first call."""
    global _PROVIDER
    if _PROVIDER is None:
        # The tracer's shutdown at exit flushes these spans before it closes its exporter.
        _PROVIDER = TracerProvider(resource=_library_resource(), shutdown_on_exit=False)
        _PROVIDER.add_span_processor(BatchSpanProcessor(SeamSpanExporter()))
        if isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider):
            trace.set_tracer_provider(_PROVIDER)
    return _PROVIDER


def _logfire_bridge_active() -> bool:
    """Whether `devops review --logfire` configured Logfire, which then owns the agent spans."""
    from devops_cli.telemetry.logfire import get_logfire_bridge

    return get_logfire_bridge().is_active()


def install_library_spans() -> TracerProvider | None:
    """Export the library spans of this process, once; return the provider, or None when the
    tracer does not export or Logfire owns the agent spans."""
    global _AGENTS_INSTRUMENTED
    tracer = get_tracer()
    if not tracer.enabled or _logfire_bridge_active():
        return None
    with _LOCK:
        provider = _provider()
        if not _AGENTS_INSTRUMENTED:
            from pydantic_ai import Agent
            from pydantic_ai.models.instrumented import InstrumentationSettings

            Agent.instrument_all(
                InstrumentationSettings(
                    tracer_provider=provider,
                    meter_provider=NoOpMeterProvider(),
                    include_content=tracer.capture_llm_content,
                    include_binary_content=False,
                    include_model_request_parameters=False,
                )
            )
            _AGENTS_INSTRUMENTED = True
        return provider


def library_span_processor() -> BatchSpanProcessor | None:
    """A processor that exports Logfire's spans through the seam, or None when the tracer does
    not export."""
    if not get_tracer().enabled:
        return None
    return BatchSpanProcessor(SeamSpanExporter())


def instrument_gateway_client(client: httpx2.AsyncClient) -> None:
    """Make HTTP client spans for the requests of the gateway client, with their trace context.

    Only this client gets the instrumentation, so no other host gets a `traceparent` or a
    `baggage` header from it.
    """
    provider = install_library_spans()
    if provider is None:
        return
    from opentelemetry.instrumentation.httpx import HTTPX2ClientInstrumentor

    # The instrumentor types its argument as a legacy httpx client, also for httpx2.
    HTTPX2ClientInstrumentor.instrument_client(
        cast(Any, client), tracer_provider=provider, meter_provider=NoOpMeterProvider()
    )


def flush_library_spans(timeout: float) -> None:
    """Export the library spans that wait in their batch, for up to `timeout` seconds."""
    if _PROVIDER is not None:
        _PROVIDER.force_flush(int(timeout * 1000))


def reset_library_spans() -> None:
    """Export the waiting library spans, shut the provider down and stop the agent spans (used
    for testing).

    The OpenTelemetry API keeps the first global provider of the process, so after a reset the
    native MCP spans reach no provider; the agent and gateway spans take theirs by argument.
    """
    global _AGENTS_INSTRUMENTED, _PROVIDER
    dropped, _PROVIDER = _PROVIDER, None
    if dropped is not None:
        dropped.force_flush(int(DEFAULT_OTEL_DRAIN_TIMEOUT_SECONDS * 1000))
        dropped.shutdown()
    _AGENTS_INSTRUMENTED = False
    # The Logfire bridge instruments the agents too, so the default goes off either way. A
    # process that did not load pydantic-ai has no default to turn off.
    if "pydantic_ai" in sys.modules:
        from pydantic_ai import Agent

        Agent.instrument_all(False)


__all__ = [
    "SeamSpanExporter",
    "flush_library_spans",
    "install_library_spans",
    "instrument_gateway_client",
    "library_span_processor",
    "reset_library_spans",
]
