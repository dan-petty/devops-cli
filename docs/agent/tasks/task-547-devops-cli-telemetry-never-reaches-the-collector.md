# Task 547: devops-cli Telemetry Never Reaches the Collector

**Issue**: [#547](https://github.com/dan-petty/devops-cli/issues/547)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/telemetry`, `priority/p1-high`

---

## 1. Description & Objectives

devops-cli exports OTLP to `telemetry.endpoint`, `http://localhost:4318` by default, where nothing listens: the collector is a ClusterIP service. Jaeger has no services, no `devops_cli_*` metric reaches Prometheus, and the `devops-cli.json` and `ai-spend.json` dashboards are empty. The exporter fails silently.

#### Key Deliverables:
- Context & Rationale*: devops-cli exports OTLP to `telemetry.endpoint`, `http://localhost:4318` by default, where nothing listens: the collector is a ClusterIP service. Jaeger has no services, no `devops_cli_*` metric reaches Prometheus, and the `devops-cli.json` and `ai-spend.json` dashboards are empty. The exporter fails silently.
- Deliverable*: A reachable OTLP endpoint for workstations, exposed like Prometheus and Grafana, as the default; a warning or `doctor` check when export fails; verified end to end with a review's spans in Jaeger and command, review and spend metrics on their dashboards.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
