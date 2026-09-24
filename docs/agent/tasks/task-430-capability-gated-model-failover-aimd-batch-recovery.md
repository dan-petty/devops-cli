# Task 430: Capability-Gated Model Failover & AIMD Batch Recovery

**Issue**: [#430](https://github.com/dan-petty/devops-cli/issues/430)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/ai`, `priority/p0-critical`

---

## 1. Description & Objectives

Replaces capability cliff degradations with strict minimum model tier requirements (reasoning $\ge 30\text{B}$, coding $\ge 7\text{B}$). Implements Additive Increase / Multiplicative Decrease (AIMD) for embedding batch sizing to prevent permanent throughput collapse on transient latency spikes.

#### Key Deliverables:
- Context & Rationale*: Replaces capability cliff degradations with strict minimum model tier requirements (reasoning $\ge 30\text{B}$, coding $\ge 7\text{B}$). Implements Additive Increase / Multiplicative Decrease (AIMD) for embedding batch sizing to prevent permanent throughput collapse on transient latency spikes.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
