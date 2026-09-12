# Task 167: Remediate PR #164 Review Findings on Sandbox Metrics Collection

**Issue**: [#167](https://github.com/dan-petty/devops-cli/issues/167)
**PR**: TBD
**Status**: In Review
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/telemetry`

---

## 1. Description & Architectural Objectives

Remediate all 9 code review findings identified on PR #164 (`feat(telemetry): cgroup v2 metrics collection and prometheus application scraping (#108)`):

1. **Option & Help Text Alignment**:
   - Add dedicated `metrics_timeout: str` in `src/devops_cli/lang/en/help.py` describing the HTTP Prometheus scrape timeout.
   - Update `src/devops_cli/commands/sandbox.py:metrics` to use `HELP.sandbox.metrics_timeout` instead of `HELP.sandbox.timeout` (which described SIGKILL graceful stop).
   - Regenerate CLI documentation (`docs/CLI_REFERENCE.md` and `docs/commands/sandbox.md`).
2. **OpenTelemetry Tracing & Metrics Instrumentation**:
   - Wrap `devops sandbox metrics` CLI command in `trace_span("sandbox.metrics", ...)` and record invocation metrics.
   - Wrap `WorkloadSandboxEngine.metrics()` in `trace_span("sandbox.engine.metrics", ...)` and record telemetry metrics (`devops_cli.sandbox.metrics_collected`, elapsed duration).
3. **Accurate CPU Sampling Calculation**:
   - Instead of interpreting cumulative `cpu.stat:usage_usec` directly as instantaneous percent, calculate CPU utilization over an interval / delta, or relative to period quota (`cpu.max`), and record cumulative usec counter.
4. **SSRF Boundary Protection**:
   - Apply SSRF validation on Prometheus scrape URL endpoints via `validate_url_egress` or validate against local container / sandbox networking with explicit, secure rules.
5. **Preserve Scrape Error State in Snapshot**:
   - Store scrape error details in `SandboxMetricsSnapshot.scrape_error` rather than collapsing failures silently into an empty list, and ensure `is_healthy` reflects scrape failure states.
6. **Prometheus Exposition Label Unescaping**:
   - Unescape standard Prometheus text exposition format escape sequences (`\"`, `\\`, `\n`) in `parse_prometheus_exposition`.
7. **Memory Leak Trajectory & Latency Degradation Detection**:
   - In `evaluate_threshold_warnings`:
     - Detect memory leak trajectory when historical samples are available or if memory consumption growth rate is abnormal.
     - Calculate latency metrics from Prometheus histogram samples (`_sum`, `_count`, `_bucket`) and emit warnings on high latency SLAs.
8. **Network Throughput Collection**:
   - Populate `network_rx_bytes` and `network_tx_bytes` from cgroup / network stats or docker container stats.
9. **Status Label Support in Prometheus HTTP Evaluator**:
   - Support `status` labels (e.g. `status="500"`, `status=~"5.."`) in addition to `code` for detecting 5xx error rate spikes.

---

## 2. Planned Changes

1. **`src/devops_cli/lang/en/help.py`**:
   - Add `metrics_timeout` to `SandboxHelp`.
2. **`src/devops_cli/commands/sandbox.py`**:
   - Update `metrics` command option help to `HELP.sandbox.metrics_timeout`.
   - Wrap CLI execution in `trace_span("sandbox.metrics", ...)`.
3. **`src/devops_cli/sandbox/engine.py`**:
   - Wrap `WorkloadSandboxEngine.metrics()` in `trace_span("sandbox.engine.metrics", ...)`.
4. **`src/devops_cli/sandbox/models.py`**:
   - Add `scrape_error: str | None = None` and `cpu_usage_usec: int | None = None` to models.
   - Update `SandboxMetricsSnapshot.is_healthy` logic to check `scrape_error`.
5. **`src/devops_cli/sandbox/metrics.py`**:
   - Unescape Prometheus labels.
   - Calculate CPU percent over sample interval / delta.
   - Validate SSRF on metrics scrape URLs.
   - Preserve scrape errors in snapshot and emit scrape warnings.
   - Evaluate memory leak trajectory and histogram latency in threshold evaluator.
   - Populate network I/O bytes.
   - Support `status` label in HTTP metrics error rate calculation.
6. **`tests/test_sandbox_metrics.py`**:
   - Add comprehensive tests covering all 9 remediations.
7. **Documentation**:
   - Run `devops docs generate --sync-readme`.

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#167) and set status to `status/in-progress`.
- [x] Author task tracking file `docs/agent/tasks/task-167-sandbox-metrics-review-remediation.md`.
- [x] Create dedicated topic branch `fix/167-sandbox-metrics-review-remediation`.
- [x] Add unit tests in `tests/test_sandbox_metrics.py` covering all 9 remediation items.
- [x] Update `src/devops_cli/lang/en/help.py`.
- [x] Update `src/devops_cli/sandbox/models.py`.
- [x] Update `src/devops_cli/sandbox/metrics.py`.
- [x] Update `src/devops_cli/sandbox/engine.py`.
- [x] Update `src/devops_cli/commands/sandbox.py`.
- [x] Regenerate documentation (`devops docs generate --sync-readme`).
- [x] Run test suite and full CI quality gate (`devops ci`).
- [ ] Author Pull Request targeting `release/v0.2.17`.
