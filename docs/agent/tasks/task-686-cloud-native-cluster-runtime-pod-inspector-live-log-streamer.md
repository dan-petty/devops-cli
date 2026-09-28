# Task 686: Cloud-Native Cluster Runtime, Pod Inspector & Live Log Streamer (`tab-k8s`)

**Issue**: [#686](https://github.com/dan-petty/devops-cli/issues/686)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/k8s`, `priority/p0-critical`

---

## 1. Description & Objectives

Transforms the primitive 10-pod table into a live, interactive Kubernetes console.

#### Key Deliverables:
- Context & Rationale*: Transforms the primitive 10-pod table into a live, interactive Kubernetes console.
- Multi-Namespace Filtering*: Namespace selector dropdown, search query bar (`/`), and status filters (`Running`, `Pending`, `CrashLoopBackOff`, `Failed`).
- Integrated Log Streamer Drawer*: Embedded `RichLog` drawer streaming live container logs with auto-scroll and follow mode (`l`), backed by non-blocking Stern/Kubernetes log tailing.
- Cluster Health & Minikube Overview*: Node resource allocation (CPU/Memory gauges), Minikube GPU status badge (`Active` / `Fallback`), and service ingress URL table (`devops k8s configure-urls`).
- Port-Forward Daemon Manager*: Real-time list of active background port forwards (`devops k8s port-forward --status`) with one-key start and terminate controls.
- Interactive Pod Actions*: Restart pod (`r`), stream logs (`l`), view manifest YAML (`y`), or inspect pod events (`e`).
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
