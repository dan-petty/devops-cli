# Task 429: Lazy Domain-Gated MCP Tool Schema Hydration

**Issue**: [#429](https://github.com/dan-petty/devops-cli/issues/429)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/mcp`, `priority/p0-critical`

---

## 1. Description & Objectives

Partitions FastMCP tools into a core eager set (~15 high-frequency tools) and lazy domain sets (`k8s_*`, `scan_*`, `gh_*`, `tf_*`, `docker_*`, `vault_*`) hydrated on-demand, preventing tool selection precision collapse and saving ~8,000 prompt tokens per turn.

#### Key Deliverables:
- Context & Rationale*: Partitions FastMCP tools into a core eager set (~15 high-frequency tools) and lazy domain sets (`k8s_*`, `scan_*`, `gh_*`, `tf_*`, `docker_*`, `vault_*`) hydrated on-demand, preventing tool selection precision collapse and saving ~8,000 prompt tokens per turn.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
