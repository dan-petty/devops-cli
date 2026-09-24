# Task 486: Review Verification on Its Own Model Task

**Issue**: [#486](https://github.com/dan-petty/devops-cli/issues/486)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

One LLM client, built from the analysis task, serves persona review, verification and the adversarial debate. On real reviews, weighting `devops-review` toward the single-GPU 14B backend (#476) cut the median review time by 19%. It also let top-severity false positives through verification, such as "Hardcoded Secrets" reported for registry-mirror URLs. Generation benefits from the fastest pool, but verification is the check that has to hold, and today both must use the same weights.

#### Key Deliverables:
- Context & Rationale*: One LLM client, built from the analysis task, serves persona review, verification and the adversarial debate. On real reviews, weighting `devops-review` toward the single-GPU 14B backend (#476) cut the median review time by 19%. It also let top-severity false positives through verification, such as "Hardcoded Secrets" reported for registry-mirror URLs. Generation benefits from the fastest pool, but verification is the check that has to hold, and today both must use the same weights.
- Deliverable*: An `ai.tasks.verification` override (provider, model, gateway address, context window) that the verification and debate stages use, falling back to the analysis client when unset. With it, `analysis` can use the fast `devops-review` pool while `verification` uses `devops-reasoning` or a pool weighted for quality. Re-run the #476 comparison with the split in place.
- Constraint*: Verification prompts carry the page and its findings, so the verification model's window must hold what the analysis window produced.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
