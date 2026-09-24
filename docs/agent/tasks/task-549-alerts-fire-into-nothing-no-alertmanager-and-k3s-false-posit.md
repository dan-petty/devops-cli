# Task 549: Alerts Fire Into Nothing: No Alertmanager, and k3s False Positives

**Issue**: [#549](https://github.com/dan-petty/devops-cli/issues/549)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/k8s`, `priority/p1-high`

---

## 1. Description & Objectives

The stack runs with `alertmanager.enabled: false`; 12 alerts fire with no receiver, and Grafana's Alertmanager datasource points at nothing. `KubeControllerManagerDown`, `KubeSchedulerDown` and `KubeProxyDown` are false: k3s runs those components in its server process, and their ServiceMonitors find no targets. A node offline for maintenance keeps node, kubelet and DaemonSet alerts firing.

#### Key Deliverables:
- Context & Rationale*: The stack runs with `alertmanager.enabled: false`; 12 alerts fire with no receiver, and Grafana's Alertmanager datasource points at nothing. `KubeControllerManagerDown`, `KubeSchedulerDown` and `KubeProxyDown` are false: k3s runs those components in its server process, and their ServiceMonitors find no targets. A node offline for maintenance keeps node, kubelet and DaemonSet alerts firing.
- Deliverable*: An Alertmanager with a receiver chosen with the maintainer; k3s components scraped from k3s's embedded metrics, or their monitors and rules disabled; a maintenance silence or inhibition for planned node downtime.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
