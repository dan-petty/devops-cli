# Tasks

## 1. Behavior

- [x] 1.1 Add failing regression tests in `tests/server/test_server_service.py` for single server span and zero probe spans
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Remove `_service_trace_middleware` and configure FastAPI telemetry exclusion in `src/devops_cli/server/service.py`
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py -k "test_service_creates_single_server_span_and_no_probe_spans or test_service_tracing_middleware_adds_headers_and_skips_probes"`
- [x] 1.3 Verify `_service_trace_middleware` is not defined in `src/devops_cli/server/service.py`
  - Verification: `$ uv run python -c 'import devops_cli.server.service as s; assert not hasattr(s, "_service_trace_middleware")'`

## 2. Validation

- [x] 2.1 Run code quality and OpenSpec checks
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck,security,swallowed-failures,openspec`
- [x] 2.2 Run full CI test suite
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py`
