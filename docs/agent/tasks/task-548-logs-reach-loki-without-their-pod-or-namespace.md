# Task 548: Logs Reach Loki Without Their Pod or Namespace

**Issue**: [#548](https://github.com/dan-petty/devops-cli/issues/548)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/k8s`, `priority/p1-high`

---

## 1. Description & Objectives

fluent-bit's Kubernetes filter cannot reach the API server (`kube api upstream connection error`). In an hour Loki held two streams: one pod labelled, and about 7,700 lines from every other pod with no namespace, pod or container. Logs cannot be queried per workload, which the TUI's LogQL streamer depends on. The logging NetworkPolicy is the first suspect.

#### Key Deliverables:
- Context & Rationale*: fluent-bit's Kubernetes filter cannot reach the API server (`kube api upstream connection error`). In an hour Loki held two streams: one pod labelled, and about 7,700 lines from every other pod with no namespace, pod or container. Logs cannot be queried per workload, which the TUI's LogQL streamer depends on. The logging NetworkPolicy is the first suspect.
- Deliverable*: fluent-bit reaches the API server and every stream carries namespace, pod and container; a check or alert catches the filter failing again.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
