# Task 536: Verifier Invalidates Findings Its Own Reason Confirms

**Issue**: [#536](https://github.com/dan-petty/devops-cli/issues/536)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

The first sample validation (#505) found all three unpinned `:latest` image findings INVALIDATED,
although the verifier's own reason confirmed the defect. It had filed the finding's verification
criterion, or its fix, as the invalidation criterion it matched:
- "Line 6 contains `FROM alpine:latest`, which uses the unpinned `latest` tag", matched as
  "The FROM directive still uses 'latest' as the image tag.";
- "The Dockerfile contains a specific tag (e.g., `golang:1.22.3`) and a checksum", which is the
  fix.

These were 3 of the run's 6 found-then-dropped injections.

### Key Deliverables Completed:

- [x] **Self-refutation withdrawn** (`_without_self_refutation` in `verification.py`):
  - A matched invalidation criterion that restates the finding's verification criteria, title or
    fix (60% or more of their words, and closer to them than to the finding's invalidation
    criteria) is not a refutation.
  - A reason that states the claimed condition without negating it confirms the finding.
  - When the invalidation rests only on those, it is withdrawn, the INVALIDATED status included,
    and the finding stays unverified and in the report.
  - A genuine refutation still invalidates, even beside a restatement.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_verifier_self_refutation.py`:
    - the verification criterion, a reworded criterion, and the fix as the "invalidation";
    - no criteria and a confirming reason;
    - genuine refutations by digest, by test fixture, and beside a restatement;
    - an untouched confirmation.
  - `tests/test_review_regression_harness.py`: the run's two misread verdicts, in the golden set
    (`misread_verdicts`).
  - `tests/test_review_verification.py`: the invalidation case now matches a criterion the
    finding names as invalidating it, not its own claim.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
