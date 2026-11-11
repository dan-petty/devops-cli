# Tasks

## 1. Library spans reach the collector through the seam

Kind: behavior.

- [x] 1.1 Add failing tests (`tests/telemetry/test_library_spans.py`): an agent run with one tool call in a row span exports `invoke_agent`, `chat` and `execute_tool` under the row span, with token use, and the own span of the tool under `execute_tool`; the spans hold no prompt or tool text; a dry run sends nothing; the gateway request carries the `traceparent` of its HTTP span and a request to another host none; with the Logfire bridge on, the agent span still reaches the collector. Teach the OTLP fake to decode a protobuf trace request.
  - Verification: `$ uv run devops ci test tests/telemetry/test_library_spans.py`
- [x] 1.2 Add `telemetry/library_spans.py` (`SeamSpanExporter`, `install_library_spans`, `instrument_gateway_client`, `library_span_processor`, `flush_library_spans`, `reset_library_spans`) and register its reset in `tests/conftest.py`. Add `PROTOBUF_CONTENT_TYPE`. Call `install_library_spans` in `resolve_pydantic_ai_model` and `instrument_gateway_client` on the gateway client. Add the dependencies `opentelemetry-exporter-otlp-proto-common` and `opentelemetry-instrumentation-httpx`.
  - Verification: `$ uv run devops ci test tests/telemetry/test_library_spans.py`

## 2. One context for own and library spans

Kind: behavior.

- [x] 2.1 Keep the ids of the open own span in the OpenTelemetry API context and delete the context variables of the tracer. Add `export_encoded` and `resource_attributes`; `flush` and `reset_tracer` export the waiting library spans.
  - Verification: `$ uv run devops ci test tests/telemetry`

## 3. The exporter contract and the Logfire bridge

Kind: behavior.

- [x] 3.1 Add a contract case: a protobuf trace request reaches the fake and the loopback receiver as the span it encodes.
  - Verification: `$ uv run devops ci test tests/telemetry/test_otlp_exporter_contract.py`
- [x] 3.2 Add the seam processor to the Logfire bridge. Delete `logfire_agent_turn`, `AgentTurnHandle`, the render helpers, the token and turn counters of the bridge, their status rows and `devops telemetry test --logfire`, with their tests.
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_logfire.py tests/commands/test_telemetry_monitoring_dry_run.py tests/ai/mcp/test_mcp_tool_listing.py`

## 4. Documentation

Kind: docs.

- [x] 4.1 Describe library spans in the doc generator (docs/TELEMETRY.md), ARCHITECTURE.md, docs/TESTING.md and the OpenTelemetry page of the knowledge base; regenerate the command docs.
  - Verification: `$ uv run devops docs generate --check`
