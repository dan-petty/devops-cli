# Task 479: Reasoning Budget Tuning for the Review Pool

**Issue**: [#479](https://github.com/dan-petty/devops-cli/issues/479)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

In the tuner's cost pass, gpt-oss 20B spends its whole 200-token budget, much of it on reasoning, where the Qwen models answer in about 120 tokens. Reasoning effort is not set per deployment. The Ollama nodes may be spending serial time on reasoning a review does not need, or cutting findings short when the budget is too small.

#### Key Deliverables:
- Context & Rationale*: In the tuner's cost pass, gpt-oss 20B spends its whole 200-token budget, much of it on reasoning, where the Qwen models answer in about 120 tokens. Reasoning effort is not set per deployment. The Ollama nodes may be spending serial time on reasoning a review does not need, or cutting findings short when the budget is too small.
- Deliverable*: Measure findings and verification outcomes against reasoning effort (low, medium) and completion budget for each reasoning deployment. Set `reasoning_effort` and `max_tokens` per deployment in the gateway.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
