# Task 108: Cgroup v2 Metrics Collection & Prometheus Application Scraping

**Issue**: [#108](https://github.com/dan-petty/devops-cli/issues/108)
**PR**: TBD
**Status**: In Progress
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/telemetry`

---

## 1. Description & Architectural Objectives

Implement real-time container resource telemetry capturing cgroup v2 metrics and Prometheus application scraping on `/metrics` endpoints to detect memory leaks, resource starvation, and performance degradation under load for sandboxed workloads.

### Key Architectural Capabilities
1. **Cgroup v2 Resource Telemetry**:
   - Extraction of CPU utilization percentage, RSS/current memory, peak memory, configured memory limit, usage percentage, page faults, active tasks/pids, I/O read/write bytes, and network throughput.
   - Dual-path collection: Direct cgroup v2 filesystem reading (`/sys/fs/cgroup`) with automated fallback to container engine inspection (`docker inspect`/`docker stats`).
2. **Prometheus Exposition Format Scraper**:
   - HTTP `/metrics` scraper using `httpx2` with URL scheme validation.
   - Resilient parser for Prometheus text exposition format (counters, gauges, histograms) supporting multi-label dimensional queries.
3. **Automated Threshold Warnings & Leak Detection**:
   - Evaluator asserting resource limits (e.g. RSS > 80% limit, high CPU > 85%).
   - Warning generation on memory leak trajectory and Prometheus error rate spikes.
4. **Visual & Machine-Readable Reporting (`devops sandbox metrics`)**:
   - Rich terminal display with formatted memory/CPU tables, threshold warning callouts, and latency/request summaries.
   - Structured JSON export (`--json`) and `--dry-run` validation.
5. **Architectural Invariants**:
   - Cyclomatic complexity $\le 10$, nesting depth $\le 5$.
   - Bounded string truncation $\le 256$ chars, test coverage $\ge 90\%$.

---

## 2. Planned Changes

1. **Models (`src/devops_cli/sandbox/models.py`)**:
   - Define `CgroupV2Metrics`, `PrometheusMetric`, `SandboxMetricsSnapshot`, `ThresholdWarning`.
2. **Telemetry Submodule (`src/devops_cli/sandbox/metrics.py`)**:
   - Implement `read_cgroup_v2_metrics()`.
   - Implement `scrape_prometheus_metrics()`.
   - Implement `evaluate_threshold_warnings()`.
   - Implement `collect_sandbox_metrics()`.
3. **Engine Integration (`src/devops_cli/sandbox/engine.py` & `__init__.py`)**:
   - Expose `WorkloadSandboxEngine.metrics()`.
4. **CLI Command (`src/devops_cli/commands/sandbox.py`)**:
   - Implement `devops sandbox metrics [identifier]` with table/json rendering and dry-run support.
5. **Localization (`src/devops_cli/lang/en/help.py`, `messages.py`)**:
   - Add help docstrings and messages.
6. **Submodule Tests (`tests/test_sandbox_metrics.py`)**:
   - Comprehensive test suite covering cgroup parsing, mock Prometheus endpoints, threshold alerts, CLI command, and dry-run.

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#108) and set label to `status/in-progress`.
- [x] Author task tracking file `docs/agent/tasks/task-108-sandbox-metrics-cgroup-prom.md`.
- [x] Create dedicated topic branch `feat/108-sandbox-metrics-cgroup-prom`.
- [x] Author test suite in `tests/test_sandbox_metrics.py`.
- [x] Implement metrics models in `src/devops_cli/sandbox/models.py`.
- [x] Implement cgroup & prometheus collector in `src/devops_cli/sandbox/metrics.py`.
- [x] Integrate metrics method in `WorkloadSandboxEngine`.
- [x] Implement CLI command in `src/devops_cli/commands/sandbox.py`.
- [x] Update language help strings in `src/devops_cli/lang/en/help.py`.
- [x] Verify test suite, complexity, Bandit, and full CI gate (`devops ci`).
- [x] Synchronize documentation (`devops docs generate --sync-readme`).
- [ ] Author Pull Request targeting `release/v0.2.17` and verify CI checks pass.
