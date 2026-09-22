# Task 433: Construct-Aware Location Validation

**Issue**: [#433](https://github.com/dan-petty/devops-cli/issues/433)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

`_check_line_boundaries` invalidates a finding only when its line number exceeds the file length. A location that is in-bounds but points at unrelated code passes untouched, so a finding can describe a real defect while sending the reader — or an auto-fix stage — to the wrong construct. Observed: a genuine SSRF finding cited an HTML tag handler roughly 170 lines from the vulnerable function.

#### Key Deliverables:
- Context & Rationale*: `_check_line_boundaries` invalidates a finding only when its line number exceeds the file length. A location that is in-bounds but points at unrelated code passes untouched, so a finding can describe a real defect while sending the reader — or an auto-fix stage — to the wrong construct. Observed: a genuine SSRF finding cited an HTML tag handler roughly 170 lines from the vulnerable function.
- Remediation*: After bounds checking, verify the cited span actually contains the construct the finding names (symbol, call, decorator, or literal) using the AST utilities already used by `_check_missing_symbol_hallucination`. On mismatch, attempt relocation by symbol search and record the correction; invalidate only when the construct is absent from the file entirely. Wrong-but-recoverable locations should be repaired, not discarded.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
