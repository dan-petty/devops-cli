# Task 167: Remediate PR #164 Review Findings on Sandbox Metrics Collection

**Issue**: [#167](https://github.com/dan-petty/devops-cli/issues/167)
**PR**: [#168](https://github.com/dan-petty/devops-cli/pull/168)
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

### Additional PR #168 Review Refinements
- URL & Error Credential Sanitization: Apply `mask_uri_credentials` and `redact_text` in `scrape_prometheus_metrics`.
- Zero Memory Current Handling: Fix `_calculate_memory_percent` with `is not None` to correctly return `0.0%`.
- Prometheus Exposition Timestamp: Preserve timestamp in `_parse_metric_line`.
- Open File Descriptors Metric: Add `open_fds_count` to `CgroupV2Metrics` and table display.
- Configured / Optional Latency SLA: Add `--latency-sla-ms` option and evaluate only when configured.
- Separate Scrape Errors from Threshold Warnings: Keep scrape failures in `snapshot.scrape_error` and render distinct `SCRAPE WARNING`.

---

## 2. Planned Changes

1. **`src/devops_cli/lang/en/help.py`**:
   - Add `metrics_timeout` and `latency_sla_ms` to `SandboxHelp`.
2. **`src/devops_cli/commands/sandbox.py`**:
   - Update `metrics` command option help to `HELP.sandbox.metrics_timeout` and add `--latency-sla-ms`.
   - Wrap CLI execution in `trace_span("sandbox.metrics", ...)`.
   - Render open FDs and distinct scrape warnings in table output.
3. **`src/devops_cli/sandbox/engine.py`**:
   - Wrap `WorkloadSandboxEngine.metrics()` in `trace_span("sandbox.engine.metrics", ...)`.
   - Add `latency_sla_ms` parameter.
4. **`src/devops_cli/sandbox/models.py`**:
   - Add `scrape_error: str | None = None`, `cpu_usage_usec: int | None = None`, and `open_fds_count: int | None = None`.
   - Update `SandboxMetricsSnapshot.is_healthy` logic to check `scrape_error`.
5. **`src/devops_cli/sandbox/metrics.py`**:
   - Unescape Prometheus labels and preserve sample timestamps.
   - Calculate CPU percent over sample interval / delta.
   - Validate SSRF and mask credentials/redact errors on metrics scrape URLs.
   - Preserve scrape errors in snapshot, separate from threshold warnings.
   - Evaluate memory leak trajectory and optional latency SLA in threshold evaluator.
   - Populate network I/O bytes and open FDs.
   - Support `status` label in HTTP metrics error rate calculation.
6. **`tests/test_sandbox_metrics.py`**:
   - Add comprehensive tests covering all 9 remediations and 6 refinements.
7. **Documentation**:
   - Run `devops docs generate --sync-readme`.

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#167) and set status to `status/in-progress`.
- [x] Author task tracking file `docs/agent/tasks/task-167-sandbox-metrics-review-remediation.md`.
- [x] Create dedicated topic branch `fix/167-sandbox-metrics-review-remediation`.
- [x] Add unit tests in `tests/test_sandbox_metrics.py` covering all 9 remediation items and 6 refinements.
- [x] Update `src/devops_cli/lang/en/help.py`.
- [x] Update `src/devops_cli/sandbox/models.py`.
- [x] Update `src/devops_cli/sandbox/metrics.py`.
- [x] Update `src/devops_cli/sandbox/engine.py`.
- [x] Update `src/devops_cli/commands/sandbox.py`.
- [x] Regenerate documentation (`devops docs generate --sync-readme`).
- [x] Run test suite and full CI quality gate (`devops ci`).
- [x] Author Pull Request targeting `release/v0.2.17` ([#168](https://github.com/dan-petty/devops-cli/pull/168)).
