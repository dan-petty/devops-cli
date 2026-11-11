# Proposal: #4510

## Why

#4510: you cannot go from a roadmap Service log line in Loki to its trace in Tempo. The Service writes each record as one JSON line to stdout, and 0 of 7,251 `roadmap-service` lines in 6 hours carry a trace id (2026-11-11). Three causes:

- `JsonLogFormatter` writes only the keys of `CONTEXT_LOG_KEYS`, and `trace_id` and `span_id` are not in it.
- No record that the `json` handler gets goes through `TraceCorrelationFilter`. The telemetry setup puts that filter on the root logger, and a logger filter runs only for records logged on that logger, not for records that propagate to it. The Service config sets the `devops_cli` and `uvicorn` loggers to `propagate: False`.
- The Grafana Loki derived field regex `(?:trace_id|traceId|traceID)[=:]...` does not match `"trace_id":"..."`, because a `"` comes between the key and the `:`.

## What Changes

- The `json` handler of `service_log_config` gets `TraceCorrelationFilter`, so each record the handler gets carries the ids of the span that is open when it is logged: a span of the own tracer, else the current OpenTelemetry span.
- `JsonLogFormatter` writes `trace_id` and `span_id` when they are not empty. A line written with no open span has neither key.
- The Loki data source in `k8s/monitoring/grafana-values.yaml` gets a regex derived field that also matches the JSON key form, and a second, label derived field that reads the `trace_id` structured metadata of OTLP log records. `trace_id` does not become a stream label.
- The Service output and a manifest change, so the change has spec deltas: an ADDED requirement in `roadmap-service-logs` and a MODIFIED requirement in `command-telemetry`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-logs`: a Service JSON line carries the ids of the open span.
- `command-telemetry`: the Loki data source links a JSON line and an OTLP log record to Tempo.

## Impact

- `src/devops_cli/server/json_logs.py`
- `k8s/monitoring/grafana-values.yaml` (Argo CD app `grafana` syncs it from `main`)
- `tests/server/test_service_log_trace_ids.py` (new)

## Feasibility

- Loki, 2026-11-11: `sum(count_over_time({service_name="roadmap-service"} |~ "trace_?[iI]d" [6h]))` is 0 of 7,251 lines. `sum by (logger) (count_over_time({service_name="roadmap-service", stream="stdout"} | json | __error__="" [6h]))` shows the loggers: 5,223 `uvicorn.access` lines, 635 webhook lines and about 2,000 job lines from `devops_cli.roadmap.*`, `devops_cli.github.*`, `devops_cli.ai.*` and `devops_cli.server.service`.
- The Service opens a span for each worker round and batch (`server/service.py`, `_execute_scoped` and `_execute_batch`) and for each HTTP request that is not a probe (`_service_trace_middleware`), so job lines and webhook lines are written in a span.
- Python logging documentation (3.14, "Filter Objects"): a filter on a handler is consulted before the handler emits an event; a filter on a logger is consulted only when an event is logged on that logger. The `dictConfig` schema takes a `filters` list on a handler.
- Grafana source, `public/app/features/loki-helpers/types.ts`: `matcherType?: 'label' | 'regex'`. The Grafana Loki data source documentation ("Derived fields") says a Label field matches indexed labels, parsed labels and structured metadata.
- The new tests fail on the base for the three cases above and pass with the change.

## Existing Tool Considered

- `opentelemetry-instrumentation-logging` (`LoggingInstrumentor`) sets `otelTraceID` and `otelSpanID` on each record through a record factory. It reads only the OpenTelemetry API context. The Service spans come from the own tracer, whose ids live in its own context variables (`telemetry/tracer.py`), so the instrumentor would write zero ids. The change uses `TraceCorrelationFilter`, which the project already has and which reads both the own tracer and the OpenTelemetry API context through `get_current_span_context`. When the own tracer is replaced by the OpenTelemetry SDK (#2536), the instrumentor becomes the tool to use.
- `python-json-logger` formats JSON lines, but it writes only the attributes that a filter put on the record, so it needs the same filter. A swap of the formatter does not change this item.
- Cost to build: about 20 changed lines in source and 130 lines of tests; about 60,000 tokens and 1 hour to build, and no separate upkeep.
- The change deletes no internal code.
