# Task 434: False-Positive Rate Tracking Across Runs

**Issue**: [#434](https://github.com/dan-petty/devops-cli/issues/434)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

`auto_record_invalidated_finding` persists every deterministically invalidated finding into the common-hallucination ledger, and `load_common_hallucinations` is exported from `ai.review` with **zero consumers** anywhere in the pipeline or the `review` command. The system records what it learned and never reads it back, so every review re-derives the same false positives at full model cost.

#### Key Deliverables:
- Context & Rationale*: `auto_record_invalidated_finding` persists every deterministically invalidated finding into the common-hallucination ledger, and `load_common_hallucinations` is exported from `ai.review` with **zero consumers** anywhere in the pipeline or the `review` command. The system records what it learned and never reads it back, so every review re-derives the same false positives at full model cost.
- Remediation*: Consume the ledger at two points — inject the highest-frequency entries as negative exemplars into persona prompts, and match new findings against it during deterministic pre-verification before an LLM call is spent. Track per-category false-positive rate across runs and surface it in the review report, so prompt changes can be evaluated against a measured baseline rather than impression.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## Scope Correction

This task was generated from a roadmap entry claiming the hallucination ledger is written and never read, with `load_common_hallucinations` having zero consumers. Half of that was wrong: `is_common_hallucination` calls it and is consumed by `_deterministic_pre_verification`, so the ledger has always been matched against new findings before an LLM call.

The half that was genuinely missing -- rendering the ledger as negative exemplars into the persona prompt, so a recorded false positive is prevented at generation rather than suppressed after -- was delivered in #404.

What remains here is per-category false-positive rate tracked across runs and surfaced in the review report, so a prompt change can be evaluated against a measured baseline. That overlaps with the prompt benchmarking work and should be built with it rather than separately.
