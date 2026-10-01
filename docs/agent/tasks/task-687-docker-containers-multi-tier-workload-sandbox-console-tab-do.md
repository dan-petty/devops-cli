# Task 687: Docker Containers & Multi-Tier Workload Sandbox Console (`tab-docker`)

**Issue**: [#687](https://github.com/dan-petty/devops-cli/issues/687)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Comprehensive workstation container and sandbox observability hub.

#### Key Deliverables:
- Context & Rationale*: Comprehensive workstation container and sandbox observability hub.
- Multi-Tier Sandbox Inspector*: Dedicated view of running Docker and Kubernetes sandboxes (`devops sandbox status`) showing active network modes (`isolated`, `sandbox_namespace`, `public_whitelist`, `local_whitelist`), cgroup resource limits, and health probe states.
- Container Performance Metrics*: Live CPU %, memory RSS vs limit, block I/O, and network throughput sparklines.
- Interactive Sandbox Controls*: Terminate sandbox (`k`), stream sandbox diagnostic logs (`l`), trigger dynamic health probe (`p`), or prune dangling volumes and images.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
