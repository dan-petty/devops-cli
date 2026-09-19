# Task 319: OpenTelemetry W3C Traceparent Context Propagation, Metric SDK & Span Waterfall Optimization Research

**Issue**: [#319](https://github.com/dan-petty/devops-cli/issues/319)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/telemetry`, `priority/p1-high`

---

## 1. Description & Objectives

Distributed tracing currently initializes basic trace providers with single-span exports, lacking automated trace context propagation across background workers, subagent tasks, and CLI child processes.

#### Key Deliverables:
- Context & Rationale*: Distributed tracing currently initializes basic trace providers with single-span exports, lacking automated trace context propagation across background workers, subagent tasks, and CLI child processes.
- Deep Integration & Functional Extension*: Automated W3C Trace Context propagation across all background tasks, subagent delegations, and external CLI subprocesses; in-process metric stream aggregation via OpenTelemetry Metrics SDK; baggage propagation for multi-persona review sessions.
- Code Optimization & Performance Acceleration*: Replace ad-hoc timing and stopwatch counters with standardized, low-overhead in-memory span processors; eliminate unhandled span export exceptions during offline operations via bounded ring-buffered exporters.
- Refactoring Potential & Legacy Elimination*: Refactor `src/devops_cli/telemetry/` into an unobtrusive decorator and context manager pattern; remove redundant manual span creation boilerplate; eliminate orphaned span traces.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
