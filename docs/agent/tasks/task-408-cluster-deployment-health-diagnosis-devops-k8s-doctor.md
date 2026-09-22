# Task 408: Cluster Deployment Health Diagnosis (`devops k8s doctor`)

**Issue**: [#408](https://github.com/dan-petty/devops-cli/issues/408)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/k8s`, `priority/p1-high`

---

## 1. Description & Objectives

A review of live cluster logs surfaced failures that are individually obvious and collectively invisible, because nothing correlates them. A node left `NotReady,SchedulingDisabled` had `metrics-server` retrying it every 12 seconds — six restarts and a log filled entirely with one unreachable host — while a `PersistentVolume` delete had been timing out for three days behind a helper pod stuck `Terminating`. Each is a one-line symptom; none is reported anywhere an operator looks.

#### Key Deliverables:
- Context & Rationale*: A review of live cluster logs surfaced failures that are individually obvious and collectively invisible, because nothing correlates them. A node left `NotReady,SchedulingDisabled` had `metrics-server` retrying it every 12 seconds — six restarts and a log filled entirely with one unreachable host — while a `PersistentVolume` delete had been timing out for three days behind a helper pod stuck `Terminating`. Each is a one-line symptom; none is reported anywhere an operator looks.
- Deliverable*: A diagnostic that correlates node readiness, pod restart counts, `Warning` events and container log error rates into a ranked list of deployment problems, naming the resource, the likely cause and the remediation. Ships as a command and as a dashboard panel.
- Constraint*: It must distinguish a cluster fault from a workload fault. Reporting `metrics-server` as unhealthy when the actual fault is a cordoned node sends the operator to the wrong place — which is precisely what the raw logs already do.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
