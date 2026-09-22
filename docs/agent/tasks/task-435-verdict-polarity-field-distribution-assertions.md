# Task 435: Verdict Polarity & Field Distribution Assertions

**Issue**: [#435](https://github.com/dan-petty/devops-cli/issues/435)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Two review-quality failures are invisible to the current schema. **Polarity**: a finding asserted a status field was "always set to ERROR" where the exported value was OK — a real defect with inverted meaning and wrong severity, which verification passed at high confidence because nothing compared observed against expected. **Distribution**: `reportable` was `true` for all 286 findings including the 7 never verified; a verdict field that never comes back false is a column, not a filter.

#### Key Deliverables:
- Context & Rationale*: Two review-quality failures are invisible to the current schema. **Polarity**: a finding asserted a status field was "always set to ERROR" where the exported value was OK — a real defect with inverted meaning and wrong severity, which verification passed at high confidence because nothing compared observed against expected. **Distribution**: `reportable` was `true` for all 286 findings including the 7 never verified; a verdict field that never comes back false is a column, not a filter.
- Remediation*: Require findings to carry `observed_value` and `expected_value` when asserting a concrete value, and reject the pair when identical. Add a pipeline self-test asserting that a finding constructed to be withdrawn is in fact withdrawn, and emit verdict-field distributions in the run summary so a field that never discriminates is visible immediately.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
