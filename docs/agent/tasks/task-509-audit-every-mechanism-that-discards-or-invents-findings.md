# Task 509: Audit Every Mechanism That Discards or Invents Findings, With a Regression Harness

**Issue**: [#509](https://github.com/dan-petty/devops-cli/issues/509)
**Status**: In Progress
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/bug`, `scope/review`, `priority/p0-critical`

---

## 1. Description & Objectives

A finding passes through deterministic pre-verification checks, the hallucinations catalog and its
learning loop, LLM verification and debate, merging, reranking, suppression, redaction and the
report's filters. Each can discard a real defect or keep a false one. The missing-symbol check
invalidated real "missing check" findings and taught them to the catalog (#500). On a synthetic
corpus of 10 known defects, the personas found 7 and 1 survived verification (#415).

#### Key Deliverables:
- An audit of every mechanism, from persona prompts and page building through to the report
  filter. Each misfire is confirmed by a reproducing test or a replay of recorded sessions
  (`candidates.json`), then fixed or filed.
- A CI regression harness that runs the deterministic layers over golden real-defect findings,
  which must survive, and known hallucinations, which must still be caught.
- Auto-learned catalog entries can be listed and removed; an entry learned from a deterministic
  invalidation is never applied without that check's ground truth.
- The golden findings come from injected defects and human-verified records, never from the
  verifier being tested.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
