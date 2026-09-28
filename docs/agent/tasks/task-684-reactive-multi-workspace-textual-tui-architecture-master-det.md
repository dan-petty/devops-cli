# Task 684: Reactive Multi-Workspace Textual TUI Architecture & Master-Detail Navigation (`devops dashboard`, `devops tui`)

**Issue**: [#684](https://github.com/dan-petty/devops-cli/issues/684)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/cli`, `priority/p0-critical`

---

## 1. Description & Objectives

Modernizes the basic Textual dashboard from static read-only tables into a reactive, multi-workspace workstation command center with non-blocking async workers (`work()`), real-time push events, and master-detail ergonomic split screens (navigation tree/list on left, contextual detail inspector with YAML/logs/markdown on right).

#### Key Deliverables:
- Context & Rationale*: Modernizes the basic Textual dashboard from static read-only tables into a reactive, multi-workspace workstation command center with non-blocking async workers (`work()`), real-time push events, and master-detail ergonomic split screens (navigation tree/list on left, contextual detail inspector with YAML/logs/markdown on right).
- Unified Workspaces*: Seamlessly tabs between 7 domain workspaces: (1) `PR & Git Lifecycle`, (2) `K8s & Minikube`, (3) `Docker & Sandboxes`, (4) `SecOps & Vault`, (5) `GitOps & ArgoCD`, (6) `AI Constellation & Memory`, and (7) `Telemetry & Loki Logs`.
- Stateful Navigation*: Preserves active table selections, scroll positions, and filter queries across tab switches with URL-like hash routing.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
