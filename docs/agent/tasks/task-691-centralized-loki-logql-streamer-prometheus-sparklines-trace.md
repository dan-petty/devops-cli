# Task 691: Centralized Loki LogQL Streamer, Prometheus Sparklines & Trace Waterfalls (`tab-telemetry`)

**Issue**: [#691](https://github.com/dan-petty/devops-cli/issues/691)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/telemetry`, `priority/p1-high`

---

## 1. Description & Objectives

Unifies the complete observability triad directly within the terminal UI.

#### Key Deliverables:
- Context & Rationale*: Unifies the complete observability triad directly within the terminal UI.
- Loki Centralized LogQL Query Console*: Embedded LogQL query input bar with syntax highlighting and live streaming log console, querying cluster-wide Fluent Bit / Loki logs without leaving the TUI.
- Prometheus Performance Sparklines*: Terminal ASCII sparklines and gauges rendering real-time command execution latencies, LLM token throughput (tokens/sec), and cache hit ratios.
- Trace Waterfall Modal*: Visual breakdown of recent OpenTelemetry distributed traces and multi-persona review spans with service latency waterfalls.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
