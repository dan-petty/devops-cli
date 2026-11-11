# Design

## Context

The own tracer builds OTLP/JSON and sends each span when it ends (`telemetry/tracer.py`). #2536 plans to move the own spans onto the SDK. This change does the part that library spans need now, and leaves the own encoding to #2536.

## Decisions

- **One provider for each process.** The OpenTelemetry API sets a global provider once for each process. `install_library_spans` makes the provider on the first call and sets it as the global provider when no other provider is set, so the native MCP spans reach it. The pydantic-ai and httpx instrumentation get the provider by argument, so they do not depend on the global one. A reset (tests) turns off the agent spans and keeps the provider.
- **Where it starts.** `resolve_pydantic_ai_model` calls it: every pydantic-ai model of devops-cli goes through it (`build_agent`, the tier models of implement, Jev). A process that builds no model loads no SDK (#858).
- **The exporter.** `SeamSpanExporter` asks `get_tracer()` for the tracer of the moment, so a test that installs the OTLP fake gets the library spans too. It drops a batch when the tracer does not export or the invocation is a dry run; the dry-run state is process-wide, so the batch thread reads it. `export_encoded` counts each request in the same success and failure counts as the own exports, so `devops telemetry status` shows both.
- **Flush and exit.** The provider does not shut down at exit by itself (`shutdown_on_exit=False`). `OTelTelemetryClient.flush`, which the tracer's shutdown at exit calls, exports the waiting library spans before it closes the exporter. `reset_tracer` exports them before it drops the tracer, so they go to the tracer that was current.
- **One context.** An own span attaches a `NonRecordingSpan` with its ids to the OpenTelemetry API context and detaches it when it ends. A new own span reads its parent from that context, so the parent is the innermost span, own or of a library. `current_trace_id`, `current_span_id` and `get_current_span_context` read the same context.
- **Content.** `include_content` follows `telemetry.capture_llm_content`. `include_model_request_parameters=False` keeps the full tool schema out of each `chat` span; pydantic-ai still writes `gen_ai.tool.definitions`. Tempo cuts each attribute at 2,048 bytes by default.
- **The Logfire bridge.** When `devops review --logfire` configured Logfire, Logfire owns the agent instrumentation and the global provider. `install_library_spans` then does nothing, and the bridge adds a `BatchSpanProcessor(SeamSpanExporter())` to its processors.
- **The resource.** The library spans take the resource of the own spans, without `telemetry.sdk.*`, through `Resource.create`, so they also read `OTEL_RESOURCE_ATTRIBUTES` and `OTEL_SERVICE_NAME`.

## Rejected alternatives

- **`logfire.configure(send_to_logfire=False, additional_span_processors=[...])` for every process.** It also adds the stock OTLP exporters when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, gives each process a random `service.instance.id`, and sets global meter and logger providers. The plain SDK provider does the same export with none of these.
- **Convert each library span to the own OTLP/JSON dict.** That adds hand-built encoding, which #2536 deletes.
- **`logfire.instrument_httpx()` or the instrumentor for every client.** It puts `traceparent` and `baggage` on every request, GitHub included.
- **`logfire.instrument_mcp`.** The native MCP spans already exist; both together make two spans for each call.
- **Keep `logfire_agent_turn` beside the library spans.** It wrote prompt text that the content setting did not gate, and the `invoke_agent` span replaces it.
