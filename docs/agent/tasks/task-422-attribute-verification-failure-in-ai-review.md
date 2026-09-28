# Task 422: Attribute Verification Failure in AI Review

**Issue**: [#422](https://github.com/dan-petty/devops-cli/issues/422)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

`_validate_segment_findings` wraps the entire LLM verification call in `except Exception: pass` and returns the unverified result (`src/devops_cli/ai/review/verification.py`). Findings are correctly rendered `*(unverified)*` rather than dropped, so nothing is lost — but an infrastructure failure, a malformed model response and a genuine refusal to verify all produce the identical output. A reviewer reading a page of unverified findings cannot tell whether the verifier disagreed or never ran.

#### Key Deliverables:
- Context & Rationale*: `_validate_segment_findings` wraps the entire LLM verification call in `except Exception: pass` and returns the unverified result (`src/devops_cli/ai/review/verification.py`). Findings are correctly rendered `*(unverified)*` rather than dropped, so nothing is lost — but an infrastructure failure, a malformed model response and a genuine refusal to verify all produce the identical output. A reviewer reading a page of unverified findings cannot tell whether the verifier disagreed or never ran.
- Deliverable*: Distinguish the outcomes. Record the failure reason on the result, surface it in the review summary, and count verification errors separately from unverified findings.
- Constraint*: Verification must stay best-effort — a model outage should degrade the review, not abort it. The change is to make the degradation legible, not to make it fatal.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
