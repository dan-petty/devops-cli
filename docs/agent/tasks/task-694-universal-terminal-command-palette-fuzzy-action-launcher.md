# Task 694: Universal Terminal Command Palette & Fuzzy Action Launcher

**Issue**: [#694](https://github.com/dan-petty/devops-cli/issues/694)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

High-velocity keyboard workflow allowing developers to execute any DevOps CLI command without exiting the TUI.

#### Key Deliverables:
- Context & Rationale*: High-velocity keyboard workflow allowing developers to execute any DevOps CLI command without exiting the TUI.
- Modal Launcher (`Ctrl+P` / `:`)*: Fast fuzzy-search command palette listing all CLI subcommands (`ci run`, `scan trivy`, `release status`, `argo sync`, `vault sync`, `sandbox iterate`).
- Non-Blocking Command Output Drawer*: Executes commands in a non-blocking background thread, streaming output directly into an ephemeral sliding terminal drawer.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
