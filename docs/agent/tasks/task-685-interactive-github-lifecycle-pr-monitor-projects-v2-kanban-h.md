# Task 685: Interactive GitHub Lifecycle, PR Monitor & Projects v2 Kanban Hub (`tab-github`)

**Issue**: [#685](https://github.com/dan-petty/devops-cli/issues/685)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/github`, `priority/p0-critical`

---

## 1. Description & Objectives

Embeds full GitHub engineering workflow visibility directly inside the terminal.

#### Key Deliverables:
- Context & Rationale*: Embeds full GitHub engineering workflow visibility directly inside the terminal.
- Chronological FIFO PR Queue*: Live pull request queue prioritized from oldest to newest with status badges (CI check conclusion, Copilot review settling indicator, unresolved review threads counter). Selecting a PR opens an inspector pane with commit diff summary and failing check logs.
- Interactive Actions*: Instant keybinding triggers to run readiness checks (`p` -> `devops pr check-readiness`), view failing run logs (`v` -> `devops gh runs view`), or open PR in browser (`o`).
- Projects v2 Mini-Kanban*: Responsive columnar view showing active milestone issues across `Backlog`, `Ready`, `In Progress`, `In Review`, and `Done` with taxonomy labels.
- API Quota Gauge*: Live visual token-bucket meter displaying remaining GitHub REST/GraphQL rate limits and reset countdown (`devops gh rate-limit`).
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
