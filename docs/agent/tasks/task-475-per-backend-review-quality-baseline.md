# Task 475: Per-Backend Review Quality Baseline

**Issue**: [#475](https://github.com/dan-petty/devops-cli/issues/475)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

Gateway weights are set by throughput alone, while three different models serve `devops-review`: Qwen2.5-Coder 32B, Qwen2.5-Coder 14B and gpt-oss 20B. A faster backend that reports more false positives, or misses defects, costs more than it saves, because every finding goes through verification. Nothing measures findings or verification outcomes by serving model.

#### Key Deliverables:
- Context & Rationale*: Gateway weights are set by throughput alone, while three different models serve `devops-review`: Qwen2.5-Coder 32B, Qwen2.5-Coder 14B and gpt-oss 20B. A faster backend that reports more false positives, or misses defects, costs more than it saves, because every finding goes through verification. Nothing measures findings or verification outcomes by serving model.
- Deliverable*: Run the same corpus through each model group directly (`devops-reasoning`, `devops-coder`, `ollama/gpt-oss:20b`) and compare findings, verification outcomes, recall on the synthetic defect corpus and false-positive rates. Decide whether routing weights need a quality factor.
- Constraint*: Ground truth must not come from the verifier being measured; see Model-in-the-Loop Prompt Benchmarking. Pool runs need the serving backend recorded per call.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
