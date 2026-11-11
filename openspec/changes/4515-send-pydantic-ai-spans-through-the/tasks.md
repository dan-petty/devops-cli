# Tasks

## 1. Library spans reach the collector through the seam

Kind: behavior.

- [x] 1.1 Add failing tests (`tests/telemetry/test_library_spans.py`): an agent run with one tool call in a row span exports `invoke_agent`, `chat` and `execute_tool` under the row span, with token use, and the own span of the tool under `execute_tool`; the spans hold no prompt or tool text; a dry run sends nothing; the gateway request carries the `traceparent` of its HTTP span and a request to another host none; the Logfire bridge owns the agent spans and hands its spans to the collector. Teach the OTLP fake to decode a protobuf trace request.
  - Verification: `$ uv run devops ci test tests/telemetry/test_library_spans.py`
- [x] 1.2 Add `telemetry/library_spans.py` (`SeamSpanExporter`, `install_library_spans`, `instrument_gateway_client`, `library_span_processor`, `flush_library_spans`, `reset_library_spans`) and register its reset in `tests/conftest.py`. Add `PROTOBUF_CONTENT_TYPE`. Call `install_library_spans` in `resolve_pydantic_ai_model` and `instrument_gateway_client` on the gateway client. Add the dependencies `opentelemetry-exporter-otlp-proto-common` and `opentelemetry-instrumentation-httpx`.
  - Verification: `$ uv run devops ci test tests/telemetry/test_library_spans.py`

## 2. One context for own and library spans

Kind: behavior.

- [x] 2.1 Keep the ids of the open own span in the OpenTelemetry API context and delete the context variables of the tracer. Add `export_encoded` and `resource_attributes`; `flush` and `reset_tracer` export the waiting library spans. Lower the swallowed-failures ceilings of `tracer.py` and `logfire.py`.
  - Verification: `$ uv run devops ci test tests/telemetry`

## 3. The exporter contract and the Logfire bridge

Kind: behavior.

- [x] 3.1 Add a contract case: a protobuf trace request reaches the fake and the loopback receiver as the span it encodes.
  - Verification: `$ uv run devops ci test tests/telemetry/test_otlp_exporter_contract.py`
- [x] 3.2 Add the seam processor to the Logfire bridge. Delete `logfire_agent_turn`, `AgentTurnHandle`, the render helpers, the token and turn counters of the bridge, their status rows and `devops telemetry test --logfire`, with their tests.
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_logfire.py tests/commands/test_telemetry_monitoring_dry_run.py tests/ai/mcp/test_mcp_tool_listing.py`

## 4. Review fixes: no Logfire cloud, no trace context to MCP

Kind: behavior.

- [x] 4.1 Add failing tests: the bridge configures Logfire with `send_to_logfire=False` and no token while `LOGFIRE_TOKEN` is set; the bridge refuses to start while an `OTEL_EXPORTER_OTLP_*ENDPOINT` variable is set; an MCP tool request in a row span with baggage holds no `traceparent`, `tracestate` or `baggage` in its `_meta`.
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_logfire.py tests/telemetry/test_library_spans.py`
- [x] 4.2 Make the bridge local only and delete `telemetry.logfire_token`, `telemetry.logfire_send_to_logfire`, `get_logfire_token`, the `logfire_token` keyring entry and the token rows of the bridge status. Add `confine_api_propagation` and call it before an own span enters the API context, before the library provider is made and before the bridge configures Logfire; the gateway client injects with its own propagator in the instrumentor's request hook.
  - Verification: `$ uv run devops ci test tests/telemetry tests/security/test_config_declarations.py tests/commands/test_config_audit_keys.py tests/ai/mcp/test_mcp_tool_listing.py`

## 5. Documentation

Kind: docs.

- [x] 5.1 Describe library spans in the doc generator (docs/TELEMETRY.md), ARCHITECTURE.md, docs/TESTING.md and the OpenTelemetry page of the knowledge base; regenerate the command docs.
  - Verification: `$ uv run devops docs generate --check`
