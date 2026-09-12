# Task 109: W3C Traceparent Propagation & Distributed Trace Correlation (`devops sandbox traces`)

**Issue**: [#109](https://github.com/dan-petty/devops-cli/issues/109)
**PR**: [#178](https://github.com/dan-petty/devops-cli/pull/178)
**Status**: In Progress
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/telemetry`

---

## 1. Description & Architectural Objectives

Implement distributed trace correlation and W3C Trace Context propagation across synthetic sandbox probes, linking test executions and health probes with downstream OpenTelemetry/Jaeger application span waterfalls, and providing a terminal waterfall visualizer via `devops sandbox traces`.

### Key Architectural Capabilities

1. **Automatic W3C Trace Context (`traceparent`, `tracestate`) Propagation**:
   - Auto-inject W3C `traceparent` headers (`00-<trace_id_32>-<span_id_16>-01`) into HTTP/REST and OpenAPI probe requests (`src/devops_cli/sandbox/probe.py`).
   - Propagate active span context when present or generate deterministic synthetic root trace context when absent.
   - Record `traceparent`, `trace_id`, and `span_id` in `EndpointProbeResult.details` and `SandboxProbeReport.trace_id` for downstream correlation.

2. **Distributed Trace Correlation Engine (`src/devops_cli/telemetry/`)**:
   - Link synthetic probes with internal OpenTelemetry spans received by local in-memory buffer, OpenTelemetry Collector, Jaeger, and Logfire.
   - Query trace spans by `trace_id` from local in-memory buffer or remote Jaeger Query API (`/api/traces/{trace_id}`).

3. **Terminal Trace Waterfall Visualization (`devops sandbox traces`)**:
   - Implement `devops sandbox traces [identifier]` command in `src/devops_cli/commands/sandbox.py`.
   - Render hierarchical Gantt-style span waterfall table showing span names, hierarchical prefixes (`├─ `, `└─ `), latencies, relative offset percentages, colored execution bars, and status badges.
   - Support `--trace-id`, `--last`, `--probe` (probe and trace in single workflow), `--jaeger-url`, `--json`, and `--dry-run`.

4. **Architectural Invariants & Quality Standards**:
   - Strict cyclomatic complexity $\le 10$ and maximum nesting depth $\le 5$ project-wide.
   - Strict hostname standard: Strictly use `example.com` (no subdomains) for mock/dummy test values.
   - Maintain $\ge 90\%$ test coverage across `src/devops_cli/sandbox/` and `src/devops_cli/telemetry/`.

---

## 2. Planned Changes

1. **Telemetry Context & Shared Waterfall Utilities**:
   - `src/devops_cli/telemetry/context.py`: Enhance `inject_traceparent_headers()` to support `auto_generate=True` ensuring every probe call transmits valid W3C headers even when called outside an active span. Add `generate_traceparent()` helper.
   - `src/devops_cli/telemetry/tracer.py` (or shared helper): Expose `flatten_waterfall_tree()` and `render_waterfall_bar()` for reuse across `telemetry.py` and `sandbox.py`.
   - Add Jaeger trace query helper to fetch and parse traces from Jaeger HTTP API (`/api/traces/{trace_id}`).

2. **Sandbox Prober (`src/devops_cli/sandbox/`)**:
   - `models.py`: Add `trace_id: str | None = None` to `SandboxProbeReport`.
   - `probe.py`: Inject W3C `traceparent` header into `probe_http()`, record trace details in `EndpointProbeResult.details`, and wrap probe execution in trace spans.
   - `engine.py`: Add `traces()` method to `WorkloadSandboxEngine` to retrieve traces for a sandbox instance or target.

3. **Sandbox Traces CLI Command (`src/devops_cli/commands/sandbox.py`)**:
   - Implement `devops sandbox traces` command supporting options `--trace-id`, `--last`, `--probe`, `--jaeger-url`, `--json`, and `--dry-run`.
   - Display Rich trace waterfall table and executive summary.

4. **Language Localization (`src/devops_cli/lang/en/`)**:
   - Update `help.py` and `messages.py` with strings for `sandbox.traces`.

5. **Tests**:
   - Author `tests/test_sandbox_traces.py` testing CLI command, waterfall rendering, Jaeger query fallback, JSON serialization, and error handling.
   - Expand `tests/test_sandbox_probe.py` asserting W3C `traceparent` injection into HTTP headers and details extraction.

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#109) and set label to `status/in-progress`.
- [x] Author task tracking file `docs/agent/tasks/task-109-sandbox-traces-w3c-waterfall.md`.
- [x] Create dedicated topic branch `feat/109-sandbox-traces-w3c-waterfall`.
- [x] Author implementation plan and obtain user approval.
- [x] Implement W3C traceparent auto-injection in `src/devops_cli/telemetry/context.py`.
- [x] Update `src/devops_cli/sandbox/probe.py` and `models.py` with trace correlation.
- [x] Implement `devops sandbox traces` command in `src/devops_cli/commands/sandbox.py`.
- [x] Author tests in `tests/test_sandbox_traces.py` and `tests/test_sandbox_probe.py`.
- [x] Verify test suite and full CI quality gate (`devops ci`).
- [x] Open draft PR targeting `release/v0.2.17` ([#178](https://github.com/dan-petty/devops-cli/pull/178)).
