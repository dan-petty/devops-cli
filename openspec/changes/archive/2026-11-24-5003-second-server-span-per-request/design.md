# Design

## Decisions

- **Keep FastAPI native telemetry**: FastAPI 0.165 provides native OpenTelemetry instrumentation. It generates server spans with standard attributes such as `http.route`.
- **Exclude probe paths via `telemetry["exclude"]`**: Pass an `exclude` callable to FastAPI that checks if the request path is in `CONST_SERVICE_PROBE_PATHS`. This stops span generation for `/healthz`, `/readyz`, and `/metrics`.
- **Replace hand-written trace middleware with header middleware**: Remove `_service_trace_middleware` so the module no longer creates an extra server span. Use `_service_headers_middleware` only to attach `X-Process-Time`, `X-DevOps-Version`, `X-Trace-ID`, and `traceparent`.
- **Set `skip_specs: true`**: The change fixes an internal server tracing defect and alters no user-facing CLI capability or specification.

## Rejected Alternatives

- **Add a collector filter in OpenTelemetry Collector**: Rejected because filtering in the collector hides the defect and violates AGENTS.md rule 11.
- **Keep hand-written middleware and disable FastAPI telemetry**: Rejected because FastAPI native telemetry follows OpenTelemetry semantic conventions and integrates with ASGI context propagation.
