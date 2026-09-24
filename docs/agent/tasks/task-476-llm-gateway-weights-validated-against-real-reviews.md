# Task 476: LLM Gateway Weights Validated Against Real Reviews

**Issue**: [#476](https://github.com/dan-petty/devops-cli/issues/476)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

`devops ai gateway tune` recommends 3/5/1/2 for `devops-review` against the live 5/3/1/1, from review-sized synthetic prompts. A sweep is not a review. Page sizes vary, the pre-call check keeps large pages off the 16K backend, and verification prompts differ from persona prompts.

#### Key Deliverables:
- Context & Rationale*: `devops ai gateway tune` recommends 3/5/1/2 for `devops-review` against the live 5/3/1/1, from review-sized synthetic prompts. A sweep is not a review. Page sizes vary, the pre-call check keeps large pages off the 16K backend, and verification prompts differ from persona prompts.
- Deliverable*: Compare both configurations with the review performance baseline over several runs each. Adopt the faster one if the quality baseline shows no loss, and record the result.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
