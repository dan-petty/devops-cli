# Task 500: Missing-Symbol Check Leaves "Missing Check" Findings Alone

**Issue**: [#500](https://github.com/dan-petty/devops-cli/issues/500)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

The deterministic check for false "symbol not defined" claims (`_check_missing_symbol_hallucination`)
runs on any finding containing the word "missing", then invalidates it if a symbol it names exists.
A finding about a missing check always names the function lacking it, so real defects are
invalidated without a model, and `auto_record_invalidated_finding` teaches them to the
hallucinations catalog. On the synthetic corpus (#415) it invalidated 4 findings of injected
defects, among them "Missing inheritance depth limit in load_policy".

#### Key Deliverables:
- Apply the check only to undefined-symbol and import claims.
- Stop recording into the catalog the findings it would have invalidated under the old trigger.
- Measure on the synthetic corpus: injected defects invalidated by the check drop to zero.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
