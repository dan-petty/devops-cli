# Task 547: devops-cli Telemetry Never Reaches the Collector

**Issue**: [#547](https://github.com/dan-petty/devops-cli/issues/547)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/telemetry`, `priority/p1-high`

---

## 1. Description & Objectives

devops-cli exports OTLP to `telemetry.endpoint`, `http://localhost:4318` by default, where nothing listens: the collector is a ClusterIP service. Jaeger has no services, no `devops_cli_*` metric reaches Prometheus, and the `devops-cli.json` and `ai-spend.json` dashboards are empty. The exporter fails silently.

### Key Deliverables Completed:

- [x] **The collector is reachable from workstations**: its service is a NodePort, with the port
  left for Kubernetes to assign. Inside the cluster the service name still works.
- [x] **`devops telemetry connect`**:
  - finds the cluster's collector through kubectl: its OTLP HTTP node port, and the current
    context's API server host (a NodePort answers on every node);
  - checks it answers, and saves it as `telemetry.endpoint` with telemetry enabled;
  - says why when it cannot: a ClusterIP service, no OTLP HTTP port, or no answer;
  - writes no host name or port into the repository.
- [x] **Failures are reported**: exports count their successes and failures, and an HTTP error
  counts as a failure. When a run's exports all failed, an interactive user is told at exit, at
  most once a day per endpoint, with the command to fix it. Runs without a terminal (CI, tests)
  stay quiet.
- [x] **Exports in flight are sent, not cancelled**: shutdown gives them up to a second to finish.
  It cancelled them, so a short command's last spans were lost; one trace arrived without its
  root span.
- [x] **Metric names survive the collector**: its Prometheus remote write keeps names as sent
  (`translation_strategy: UnderscoreEscapingWithoutSuffixes`). The default unit suffixes turned
  `devops_cli_command_total` into `devops_cli_command_total_ratio`, which no dashboard queries.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_telemetry_collector_export.py`:
    - endpoint discovery, with the context flag first;
    - ClusterIP and missing-port errors;
    - `connect` saving an endpoint that answers, and keeping the configuration when it does not;
    - counted failures reported once a day to a terminal and never without one;
    - exports drained at shutdown.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

The pipeline was checked through a port-forward of the collector to `localhost:4318`, the
endpoint devops-cli already uses:
- **Traces:** Jaeger listed a `devops-cli` service, and each command's trace arrived; a review's
  had 18 spans. Before, Jaeger had no services.
- **Metrics:** `devops_cli_*` metrics reached Prometheus. The running collector still names them
  with suffixes (`devops_cli_command_total_ratio`) until these values are applied with
  `devops k8s stack`, as it is for the NodePort.

The `devops-cli` and `ai-spend` dashboards also query metrics nothing sends over OTLP: review
duration, findings, and AI spend, which only `devops server` exposes. That is #564.
