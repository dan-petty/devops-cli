# Design

The roadmap Service writes its logs through `service_log_config`, which uvicorn applies with `logging.config.dictConfig` when it starts. The config replaces the root handlers with one `json` handler and sets the `devops_cli` and `uvicorn` loggers to `propagate: False`. Alloy ships the stdout lines to Loki. The telemetry setup puts `TraceCorrelationFilter` on the root logger, but no Service record goes through it.

## Decisions

1. **The filter goes on the `json` handler.** A filter on a handler runs for each record that the handler gets, also for a record that propagates to it (Python logging documentation, "Filter Objects").
2. **The formatter writes only non-empty ids.** The filter sets `""` when no span is open. An empty key on each startup and probe line adds bytes and no link.
3. **Two derived fields.** The regex field reads a 32-character hex id after a `trace_id`, `traceId` or `traceID` key, with or without quotes around the key, so it matches JSON lines and `key=value` lines. The label field reads the `trace_id` structured metadata that the collector's Loki OTLP exporter writes.
4. **The Service keeps one log path, stdout.** Alloy already ships stdout to Loki. An OTLP log handler in the Service config would put each WARNING and ERROR line in Loki two times.

## Rejected alternatives

- **The filter on each named logger.** A logger that a later change adds to the config would have no ids. One handler filter covers each logger that writes through `json`.
- **`JsonLogFormatter` reads the span context itself.** A filter is the standard place to add context to a record, and the OTLP handler reads the same record attributes. A formatter that reads the context gives wrong ids to a record that is formatted later than it was logged.
- **A `trace_id` stream label.** Each trace would make a new Loki stream, with no bound.
- **`opentelemetry-instrumentation-logging`.** It reads only the OpenTelemetry API context, and the Service spans come from the own tracer (proposal, Existing Tool Considered).

## Risks

- `get_current_span_context` gives the own tracer's span before an OpenTelemetry span. When library spans become children of an own span (#2536), a line in a library span names the parent own span. The link still opens the right trace.
- `uvicorn.access` lines carry no ids: most are probe requests, which open no span, and uvicorn writes the line when the response starts, after the Starlette middleware has closed its span. The 90 % target counts job lines only.
