# Task 308: Docker Engine Socket API, Layer Caching Introspection & Container Sandbox Optimization Research

**Issue**: [#308](https://github.com/dan-petty/devops-cli/issues/308)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Workstation container management and dynamic sandbox execution currently execute shallow shell commands (`docker run`, `docker inspect`, `docker stats`) via subprocesses, leading to process churn and fragile string scraping.

#### Key Deliverables:
- Context & Rationale*: Workstation container management and dynamic sandbox execution currently execute shallow shell commands (`docker run`, `docker inspect`, `docker stats`) via subprocesses, leading to process churn and fragile string scraping.
- Deep Integration & Functional Extension*: Establish direct asynchronous communication over the local Docker daemon Unix domain socket (`/var/run/docker.sock`) using engine APIs; introspect BuildKit multi-stage layer caching; stream real-time container resource metrics and cgroup telemetry directly into reactive streams.
- Code Optimization & Performance Acceleration*: Eliminate subshell latency when provisioning sandboxes; streamline ephemeral image builds via BuildKit cache mounts; implement zero-overhead container health probing via socket pings.
- Refactoring Potential & Legacy Elimination*: Refactor `src/devops_cli/commands/docker.py` and `src/devops_cli/core/sandbox.py` to share a unified container engine client; replace unstructured stdout scraping with typed Pydantic container state models; eliminate legacy fallback shims.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
