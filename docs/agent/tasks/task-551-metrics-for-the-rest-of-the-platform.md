# Task 551: Metrics for the Rest of the Platform

**Issue**: [#551](https://github.com/dan-petty/devops-cli/issues/551)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/k8s`, `priority/p2-medium`

---

## 1. Description & Objectives

Beyond Kubernetes, Prometheus scrapes only Qdrant and the OpenTelemetry collector. ArgoCD, cloudflared, Valkey, the image registry, squid, and fluent-bit, Loki and Jaeger themselves run unmonitored.

#### Key Deliverables:
- Context & Rationale*: Beyond Kubernetes, Prometheus scrapes only Qdrant and the OpenTelemetry collector. ArgoCD, cloudflared, Valkey, the image registry, squid, and fluent-bit, Loki and Jaeger themselves run unmonitored.
- Deliverable*: A ServiceMonitor for each component's own metrics endpoint (ArgoCD, cloudflared, the registry, fluent-bit, Loki, Jaeger), a maintained exporter otherwise (Valkey, squid), and dashboards or alerts where they matter: ArgoCD sync and health, tunnel health, cache and proxy errors.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
