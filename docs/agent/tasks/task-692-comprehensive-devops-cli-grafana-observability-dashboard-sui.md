# Task 692: Comprehensive DevOps CLI Grafana Observability Dashboard Suite & GitOps Provisioner (`devops grafana dashboards sync`)

**Issue**: [#692](https://github.com/dan-petty/devops-cli/issues/692)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/cli`, `priority/p0-critical`

---

## 1. Description & Objectives

While the Textual TUI provides immediate interactive terminal visibility, long-term trend analysis, multi-workstation telemetry aggregation, and cluster-wide observability require enterprise-grade Grafana dashboards backed by Prometheus, Loki, and Tempo/Jaeger.

#### Key Deliverables:
- Context & Rationale*: While the Textual TUI provides immediate interactive terminal visibility, long-term trend analysis, multi-workstation telemetry aggregation, and cluster-wide observability require enterprise-grade Grafana dashboards backed by Prometheus, Loki, and Tempo/Jaeger.
- Unified Workstation & Agentic Observability Portfolio*:
- DevOps Workstation CLI & Agent Telemetry (`dashboards/devops-cli.json`)**: Subcommand invocation frequency, p50/p95/p99 execution latency histograms, exit code distributions, subagent task durations, and OpenTelemetry span waterfalls.
- AI Constellation & Priority Slot Leasing (`dashboards/ai-constellation.json`)**: Multi-node Ollama slot leasing concurrency, active leases vs. parallel limits, token generation throughput (tokens/sec), time-to-first-token (TTFT), vector cache hit ratios, and priority queue lengths (`high`, `normal`, `as_available`).
- Multi-Persona Code Review & Findings Quality (`dashboards/ai-review.json`)**: Review volume segmented by classification context (`documentation`, `configuration`, `code`), persona finding distributions (`devsecops`, `architect`, `qa`, `pm`, `auditor`), severity heatmaps, finding mitigation latency, and false-positive invalidation rates.
- GitHub Projects v2, PR Queue & API Quota (`dashboards/github-agentic.json`)**: FIFO pull request queue depth, PR readiness turnaround, Copilot review settling latency, and real-time REST/GraphQL token-bucket consumption gauges.
- Centralized Logging & Incident Triage (`dashboards/loki-incident-triage.json`)**: Loki LogQL error stream panels, trace-to-log correlation via trace ID exemplars, and SIEM audit logs.
- Automated K8s Sidecar & ConfigMap GitOps Provisioning*: Packages bundled dashboards into Kubernetes ConfigMaps labeled with `grafana_dashboard: "1"`, enabling automatic, zero-restart discovery and live reloads via the Grafana dashboard sidecar (`k8s/monitoring/prometheus-values.yaml`).
- Declarative Dashboard Linter & Exporter (`devops grafana dashboards validate`) (P1 - High)*: Automated schema validator and exporter verifying Grafana 10+ panel schema compliance, datasource parameterization (`${DS_PROMETHEUS}`, `${DS_LOKI}`), and uid idempotency across all committed dashboard definitions.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
