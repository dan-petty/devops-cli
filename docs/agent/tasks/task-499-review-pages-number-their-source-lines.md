# Task 499: Review Pages Number Their Source Lines

**Issue**: [#499](https://github.com/dan-petty/devops-cli/issues/499)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

Review pages give the model source text without line numbers, and a part of a split file starts
mid-file with no offset, so every reported line range is the model's own count. The synthetic
defect corpus (#415) caught it: an injected `mkdir(mode=0o777)` at line 248 of
`crypto/known_hosts.py` was reported at lines 106–108 and 112–115. Locations drive patching,
duplicate consolidation by line overlap and the verifier's out-of-range check.

#### Key Deliverables:
- Prefix each page line with its absolute line number, parts of split files included, and have
  the persona prompts cite those numbers.
- Measure both sides: injections matched by line on the synthetic corpus before and after, and
  prompt tokens per review from `devops review benchmark`.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
