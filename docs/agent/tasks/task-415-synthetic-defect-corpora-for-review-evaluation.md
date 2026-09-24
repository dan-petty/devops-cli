# Task 415: Synthetic Defect Corpora for Review Evaluation

**Issue**: [#415](https://github.com/dan-petty/devops-cli/issues/415)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

Evaluating a reviewer needs code whose defects are known exactly. Real repositories do not supply that — a finding is only ever labelled by another judgement, which is the circularity the benchmark above runs into. Code can instead be generated with a defect deliberately injected at a known line, giving a recall figure that is measured rather than inferred.

#### Key Deliverables:
- Context & Rationale*: Evaluating a reviewer needs code whose defects are known exactly. Real repositories do not supply that — a finding is only ever labelled by another judgement, which is the circularity the benchmark above runs into. Code can instead be generated with a defect deliberately injected at a known line, giving a recall figure that is measured rather than inferred.
- Deliverable*: A generator that takes a clean source file and an injection template — drop a bounds check, widen a path join, remove an `await`, unpin a tag — and emits the mutated file with the injected line recorded. Recall is the share of injections reported at the right location; precision is what the reviewer reports beyond them.
- Constraint*: An injection the generator knows how to make is an injection the prompt can be tuned to find, and tuning against a synthetic corpus produces a reviewer good at synthetic defects. It measures regression, not capability, and the distinction has to stay visible in how the numbers are reported.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
