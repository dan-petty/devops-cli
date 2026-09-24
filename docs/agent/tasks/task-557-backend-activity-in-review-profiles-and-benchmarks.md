# Task 557: Backend Activity in Review Profiles and Benchmarks

**Issue**: [#557](https://github.com/dan-petty/devops-cli/issues/557)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

#545's imbalance was measured with a script sampling `nvidia-smi` and vLLM queues during a review. Profiles count calls per backend, not how long each was busy or how many ran at once, so a benchmark cannot show whether a routing change spread the load.

#### Key Deliverables:
- Context & Rationale*: #545's imbalance was measured with a script sampling `nvidia-smi` and vLLM queues during a review. Profiles count calls per backend, not how long each was busy or how many ran at once, so a benchmark cannot show whether a routing change spread the load.
- Deliverable*: Profiles record per backend and stage the busy seconds and peak and mean concurrent calls, from each call's start, end and serving backend; benchmark summaries and comparisons show each backend's busy share; with #546's metrics, a command reports the pool's busy share and queue over a window.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
