# Proposal: #4515

## Why

Issue #4515: devops-cli exports its own spans through its own tracer (`src/devops_cli/telemetry/tracer.py`), and no process sets an OpenTelemetry SDK tracer provider. So the OpenTelemetry API spans of pydantic-ai (stage, refine, review, implement and the harness `Coder`), of the MCP client and of the gateway client go to the no-op provider of the API. On 2026-11-11, Tempo had one instrumentation scope, `devops-cli.telemetry`, and 0 `invoke_agent`, `chat`, `execute_tool` or MCP spans in 7 days. The own tracer kept its ids in its own context variables, so a library span could not find the row span as its parent.

`logfire_agent_turn` and `AgentTurnHandle` wrote up to 500 characters of prompt and reply text on a span, and `telemetry.capture_llm_content` did not gate them. Only `devops telemetry test --logfire` called them.

## What Changes

- A new module, `telemetry/library_spans.py`, sets one SDK `TracerProvider` for each process, when the process builds its first pydantic-ai model (`resolve_pydantic_ai_model`) and telemetry export is on. Its `BatchSpanProcessor` hands each batch to `SeamSpanExporter`, which encodes it with the official OTLP encoder and gives the protobuf body to the exporter of the process's tracer (#1319). A dry run sends nothing.
- `Agent.instrument_all` turns on the pydantic-ai spans, with `include_content` from `telemetry.capture_llm_content`, no binary content, no model request parameters and no metrics.
- The MCP client keeps its native spans, which now reach the provider. The gateway client gets the OpenTelemetry httpx instrumentor; no other client gets it.
- The tracer keeps the ids of the open span in the OpenTelemetry API context, not in its own context variables. The context variables are deleted. `export_encoded` sends an encoded request on the calling thread and counts it. `flush` also exports the waiting library spans.
- The Logfire bridge (the `--logfire` option of the review commands) adds the seam processor, so the agent spans also reach the collector. It runs Logfire as a local SDK: `send_to_logfire=False`, no token, and no start while an `OTEL_EXPORTER_OTLP_*ENDPOINT` variable is set. `telemetry.logfire_token`, `telemetry.logfire_send_to_logfire`, `get_logfire_token` and the `logfire_token` keyring entry are deleted.
- The global propagator of the OpenTelemetry API injects nothing, so an MCP request carries no trace context. The gateway client injects the trace context and baggage of its HTTP client span with its own propagator.
- Deleted, with no replacement: `logfire_agent_turn`, `AgentTurnHandle`, `render_agent_turn_table`, `render_agent_turn_panel`, the token and turn counters of the bridge, the rows of `devops telemetry logfire` that showed them, and `devops telemetry test --logfire`.
- The OTLP fake decodes a protobuf trace request. The contract suite gets a protobuf case.
- New direct dependencies, at the locked versions: `opentelemetry-exporter-otlp-proto-common==1.45.1` and `opentelemetry-instrumentation-httpx==0.66b1`.

## Capabilities

### New Capabilities

- `library-spans`: the spans of pydantic-ai, the MCP client and the gateway client, how they nest under the own spans, what they hold, and where they go.

## Impact

- `src/devops_cli/telemetry/library_spans.py` (new), `telemetry/tracer.py`, `telemetry/exporter.py`, `telemetry/logfire.py`, `telemetry/propagation.py`, `telemetry/__init__.py`, `telemetry/telemetry_plans.py`
- `src/devops_cli/config/settings.py` and `config/env.py` (the Logfire token only), `src/devops_cli/exceptions/telemetry.py` (a docstring)
- `src/devops_cli/ai/pydantic_ai_bridge.py` (`resolve_pydantic_ai_model` only), `src/devops_cli/ai/providers/__init__.py` (the gateway client only)
- `src/devops_cli/commands/telemetry.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/docs/generator.py`
- `pyproject.toml`, `uv.lock`; `tests/support/fakes/otlp.py`, `tests/conftest.py`, tests under `tests/telemetry/` and `tests/commands/`
- ARCHITECTURE.md, docs/TELEMETRY.md, docs/TESTING.md, the generated command docs and the knowledge base
- The change fits one pull request. It is the spans and propagation part of #2536 for library spans only: the own spans keep their own OTLP/JSON encoding until #2536.

## Feasibility

- **No provider today.** `git grep -n "set_tracer_provider\|instrument_all" origin/main -- src` finds nothing. Only `commands/review.py:194-208` calls `logfire.configure`, through the Logfire bridge, and the live pods set no `OTEL_EXPORTER_OTLP_ENDPOINT` (obs-cache study of 2026-11-11, `kubectl` env names).
- **pydantic-ai without Logfire.** pydantic-ai 2.59.0 documents "Using OpenTelemetry without Logfire" (https://pydantic.dev/docs/ai/integrations/logfire/). `Agent.instrument_all` sets `Agent._instrument_default` (`site:pydantic_ai/agent/__init__.py:549,1190`), and each run reads it (`:3418`), so a call before the first run is enough. `InstrumentationSettings` takes `tracer_provider`, `meter_provider`, `include_content`, `include_binary_content` and `include_model_request_parameters` (`site:pydantic_ai/models/instrumented.py:89-99`). `RequestUsage.opentelemetry_attributes` writes `gen_ai.usage.cache_read.input_tokens` (`site:pydantic_ai/usage.py:245-260`).
- **The encoder.** `opentelemetry-exporter-otlp-proto-common` 1.45.1 gives `encode_spans` (`trace_encoder/__init__.py:41`). The exporter seam takes any body and content type (`telemetry/exporter.py`, `OtlpExporter.export`), and the collector's OTLP/HTTP receiver takes `application/x-protobuf`.
- **One context.** OpenTelemetry Python keeps the active span in a `contextvars` context (`opentelemetry.context`). A `NonRecordingSpan` with a valid `SpanContext` is a parent for the SDK's default `ParentBased(ALWAYS_ON)` sampler. The new tests show the nesting both ways.
- **MCP.** The MCP SDK 2.3.0 opens client spans and puts the context in `_meta` (`site:mcp/shared/jsonrpc_dispatcher.py:387-393`), and fastmcp 4.1.2 has `client_span` (`site:fastmcp/client/telemetry.py:13`). Both use the global provider, so `logfire.instrument_mcp` would make a second span for each call.
- **httpx for one host.** `opentelemetry-instrumentation-httpx` 0.66b1 has `HTTPX2ClientInstrumentor.instrument_client` for one `httpx2` client (`site:opentelemetry/instrumentation/httpx/__init__.py:83,1556,1775`). The gateway client is unpooled and made only for the gateway (`ai/providers/__init__.py`, `gateway_caller`).
- **Why not `logfire.configure`.** Logfire 5.2.0 adds the stock `OTLPSpanExporter`, a metric reader and a log processor whenever `OTEL_EXPORTER_OTLP_ENDPOINT` is set (`site:logfire/_internal/config.py:1412-1430`). devops-cli reads that variable as a fallback endpoint, so a person who sets it would send each span twice, past the egress-checked client (SECURITY.md) and the dry-run rule (#412).
- **MCP requests carry trace context.** With an own span in the API context, fastmcp's `inject_trace_context` returned a `traceparent` (a scratch run on 64540f6a), and a new test saw `traceparent` and `baggage` in the `_meta` of a roadmap MCP tool request. `opentelemetry.propagate.set_global_textmap` replaces the global propagator, and a `TextMapPropagator` with an empty `inject` sends nothing.
- **Logfire's cloud.** Before this change the bridge set `send_to_logfire=True` when a token was set (`telemetry/logfire.py`, `elif resolved_token`). With `send_to_logfire=False`, Logfire adds no cloud exporter, also with `LOGFIRE_TOKEN` set (`site:logfire/_internal/config.py:1230`).
- **Import cost.** `pydantic_ai` already imports logfire and the OpenTelemetry SDK (measured in one interpreter: 0 s extra after `import pydantic_ai`), so the module adds no import to a process that builds a model. The startup gate (#858) keeps the SDK out of `--help`.

## Existing Tool Considered

The OpenTelemetry SDK (`TracerProvider`, `BatchSpanProcessor`, `SpanExporter`), the official encoder `opentelemetry-exporter-otlp-proto-common`, `opentelemetry-instrumentation-httpx`, the pydantic-ai instrumentation and the native MCP spans do all the work. The only new code is one thin `SpanExporter` over the seam of #1319. The stock OTLP exporters and `logfire.configure` with `OTEL_EXPORTER_OTLP_ENDPOINT` are rejected: they bypass the egress-checked client and the dry-run rule.
