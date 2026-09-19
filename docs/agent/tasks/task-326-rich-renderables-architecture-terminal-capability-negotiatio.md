# Task 326: Rich Renderables Architecture, Terminal Capability Negotiation & Universal Output Serialization Research

**Issue**: [#326](https://github.com/dan-petty/devops-cli/issues/326)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

CLI terminal formatting mixes procedural `rich.print` calls, Typer echoes, and custom table formatters, creating inconsistent visual styles and hindering machine-readable automation.

#### Key Deliverables:
- Context & Rationale*: CLI terminal formatting mixes procedural `rich.print` calls, Typer echoes, and custom table formatters, creating inconsistent visual styles and hindering machine-readable automation.
- Deep Integration & Functional Extension*: Standardized Renderables pipeline with dynamic terminal capability negotiation (detecting NO_COLOR, TTY, CI, and color depths) and universal `--json` / `--yaml` output serialization across 100% of CLI subcommands.
- Code Optimization & Performance Acceleration*: Streamline terminal output generation by replacing custom string formatting with native Rich Console protocols; eliminate redundant serialization logic across CLI commands; ensure predictable machine-readable output in CI automation.
- Refactoring Potential & Legacy Elimination*: Refactor `src/devops_cli/output.py` to replace procedural table formatting loops with declarative Pydantic-to-table mappers; standardize log levels, error alerts, and progress bars across all command modules.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
