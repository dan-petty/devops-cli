# Task 473: Review Performance Baseline Per-Stage Timing, Calls and Tokens on a Fixed Corpus

**Issue**: [#473](https://github.com/dan-petty/devops-cli/issues/473)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

End-to-end review timings are anecdotal. Three identical all-persona runs over the same 15 playbooks took 3 min 36 s to 4 min 31 s and produced 40, 53 and 70 candidate findings. Nothing splits the time between persona review, the verification debate and local work, or counts the LLM calls and tokens per stage. So the effect of gateway tuning on a review cannot be attributed. This is also the most direct tour of how `devops ai review` works.

#### Key Deliverables:
- Context & Rationale*: End-to-end review timings are anecdotal. Three identical all-persona runs over the same 15 playbooks took 3 min 36 s to 4 min 31 s and produced 40, 53 and 70 candidate findings. Nothing splits the time between persona review, the verification debate and local work, or counts the LLM calls and tokens per stage. So the effect of gateway tuning on a review cannot be attributed. This is also the most direct tour of how `devops ai review` works.
- Deliverable*: A repeatable benchmark over a fixed corpus (the homelab playbooks plus a pinned set of this repository's modules), with the response cache bypassed. For each stage it reports wall time, LLM calls, prompt and completion tokens, the serving backend, and candidate and reported findings. Results are stored as JSON so runs can be compared, and the traces are visible in Jaeger.
- Constraint*: Findings vary between identical runs, so one run measures noise. Report medians over several runs, and normalise time by the number of candidates verified.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
