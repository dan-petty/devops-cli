# Task 550: Metrics and Logs Are Kept for Two Hours

**Issue**: [#550](https://github.com/dan-petty/devops-cli/issues/550)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/k8s`, `priority/p2-medium`

---

## 1. Description & Objectives

Prometheus keeps 2 hours (512 MB) and Loki 2 hours, leaving no history for capacity and routing analysis, #477's real-traffic cost, or looking back at an incident.

#### Key Deliverables:
- Context & Rationale*: Prometheus keeps 2 hours (512 MB) and Loki 2 hours, leaving no history for capacity and routing analysis, #477's real-traffic cost, or looking back at an incident.
- Deliverable*: Retention sized to available storage, e.g. two weeks of metrics and a week of logs on persistent volumes, with an alert before a volume fills.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
