# Task: OpenTelemetry 1.45.1 and GitPython 3.2.1 Clear Two Advisories That Fail Every devops ci Audit (#1899)

**Issue**: [#1899](https://github.com/dan-petty/devops-cli/issues/1899)
**Scope**: scope/ci, scope/security
**Feasibility**: At release/v0.2.39 3c9ba76, `uv audit` reported GHSA-xcq7-p3pf-p88h against `opentelemetry-api` 1.44.0 (patched in 1.45.1) and, with that package moved, GHSA-83vg-56qc-22m7 against `gitpython` 3.2.0 (patched in 3.2.1). Both advisories were published on 2026-10-22. The pre-push `uv run devops ci` of #1892 failed only its `audit` row on them. `uv lock` with `opentelemetry-exporter-otlp-proto-grpc==1.45.1` failed, because `logfire` 5.1.0 requires `opentelemetry-sdk<1.45.0`. `logfire` 5.2.0, the latest release, allows `<1.46.0`. With the pins below, `uv audit` finds no known vulnerability in 232 packages.

## Description

- **The pins** (`pyproject.toml`). `opentelemetry-api` and `opentelemetry-exporter-otlp-proto-grpc` 1.45.1, `logfire` 5.2.0 and `gitpython` 3.2.1.
- **The lock** (`uv.lock`). The OpenTelemetry core packages move to 1.45.1 and the contrib packages to 0.66b1, because `opentelemetry-sdk` 1.45.1 requires `opentelemetry-semantic-conventions==0.66b1`. The OpenTelemetry project's `opentelemetry-exporter-http-transport` and `opentelemetry-exporter-otlp-common` 0.66b1 join the lock as dependencies of the new exporters. No other package moves.
- **The knowledge base**. `python_packages.md`, `libraries/opentelemetry.md` and `tools/opentelemetry_jaeger.md` name the new versions.

## Acceptance Criteria

- [x] `uv audit` at the branch reports no known vulnerability, and `uv lock --check` passes.
- [x] The telemetry tests pass on the new versions (`tests/test_telemetry*.py`, `tests/test_third_party_telemetry.py`, `tests/test_ai_client_telemetry.py`, `tests/test_rag_query_telemetry.py`, `tests/test_kb_manuals_metadata.py`: 149 passed, 1 skipped). The `LogfireNotConfiguredWarning` that `tests/test_telemetry_logfire.py` shows also appears with `logfire` 5.1.0.
- [x] `uv run devops ci` passes (pre-push hook).
