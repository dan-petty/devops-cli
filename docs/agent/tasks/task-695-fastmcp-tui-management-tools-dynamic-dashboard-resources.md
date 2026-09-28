# Task 695: FastMCP TUI Management Tools & Dynamic Dashboard Resources

**Issue**: [#695](https://github.com/dan-petty/devops-cli/issues/695)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/mcp`, `priority/p2-medium`

---

## 1. Description & Objectives

Exposes FastMCP tools (`dashboard_launch`, `dashboard_status`, `dashboard_switch_tab`) and dynamic system resources (`resource://dashboard/status`, `resource://dashboard/k8s`, `resource://dashboard/github`, `resource://dashboard/secops`) enabling AI assistants to query dashboard state, monitor workstation telemetry, and trigger UI focus programmatically.

#### Key Deliverables:
- Context & Rationale*: Exposes FastMCP tools (`dashboard_launch`, `dashboard_status`, `dashboard_switch_tab`) and dynamic system resources (`resource://dashboard/status`, `resource://dashboard/k8s`, `resource://dashboard/github`, `resource://dashboard/secops`) enabling AI assistants to query dashboard state, monitor workstation telemetry, and trigger UI focus programmatically.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
