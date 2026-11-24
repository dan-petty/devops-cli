# Proposal: #5003

## Why

Issue #5003: the Service creates a second server span for each request. The hand-written `_service_trace_middleware` in `src/devops_cli/server/service.py` creates one server span and skips probe paths. FastAPI native OpenTelemetry instrumentation creates a second server span for each request, including `/healthz`, `/readyz`, and `/metrics`. These duplicate spans fill the trace search and the Tempo storage.

## What Changes

- Remove `_service_trace_middleware` from `src/devops_cli/server/service.py`.
- Configure FastAPI native telemetry in `create_service_app` to exclude `CONST_SERVICE_PROBE_PATHS`.
- Add `_service_headers_middleware` to attach response timing headers (`X-Process-Time`, `X-DevOps-Version`) and trace context headers without creating a server span.
- Ensure the Service initializes library spans when tracing is enabled.
- Add regression tests in `tests/server/test_server_service.py` to verify that requests create one server span and probe requests create no server spans.
- Set `skip_specs: true` because this change alters no CLI commands or capability specifications.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Runtime: the Service creates only one server span for webhook requests, and creates no spans for probe requests.
- Storage: Tempo storage usage decreases because probe requests no longer generate spans.

## Feasibility

- FastAPI version 0.165 includes native OpenTelemetry telemetry support with an `exclude` predicate.
- The repository already imports OpenTelemetry SDK packages and wires library spans.

## Existing Tool Considered

FastAPI native telemetry (`fastapi.telemetry`) is already included in FastAPI 0.165. It creates server spans with `http.route` attributes and accepts an `exclude` function to skip probe paths.
