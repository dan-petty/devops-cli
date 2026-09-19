# Task 318: FastMCP In-Process Execution, In-Memory Tool Dispatch & Schema Caching Acceleration Research

**Issue**: [#318](https://github.com/dan-petty/devops-cli/issues/318)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/mcp`, `priority/p0-critical`

---

## 1. Description & Objectives

FastMCP tool handlers currently invoke `uv run devops <subcommand>` external subshells, incurring ~1.5s subshell initialization latency per tool invocation and causing agent response lag.

#### Key Deliverables:
- Context & Rationale*: FastMCP tool handlers currently invoke `uv run devops <subcommand>` external subshells, incurring ~1.5s subshell initialization latency per tool invocation and causing agent response lag.
- Deep Integration & Functional Extension*: Direct in-process execution of CLI tools via Python functional APIs, completely eliminating subshell spawning; lazy domain-gated tool schema hydration; dynamic MCP resource subscriptions (`resource://`) for streaming state changes directly to IDE clients.
- Code Optimization & Performance Acceleration*: Slash FastMCP tool execution latency from ~1,500ms down to <5ms (a 300x acceleration across multi-turn agent sessions); dramatically reduce process churn and CPU consumption during autonomous workflows.
- Refactoring Potential & Legacy Elimination*: Refactor `src/devops_cli/ai/mcp/server.py` to decouple MCP tool signatures from CLI command line strings; eliminate repetitive `_run_mcp_cmd` wrappers; establish direct invocation bindings to core library functions.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
