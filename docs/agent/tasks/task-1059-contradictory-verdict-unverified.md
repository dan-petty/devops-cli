# Task 1059: Contradictory Verifier Verdict Stays Unverified with Contradiction Note

**Issue**: [#1059](https://github.com/dan-petty/devops-cli/issues/1059)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: type/fix, scope/ai

---

## 1. Description & Objectives

A verifier verdict that both confirmed and refuted a finding could previously end `VERIFIED` with no verification note when its reason repeated the finding's title or matched its verification criteria without a negation word.

### Golden Case
Review session `20261003-034353` (S10, `release/v0.2.25` at `d6ebe97`, `devsecops` persona), model reply `llm_acc69d97`:
- **Finding 2** (`src/devops_cli/ai/review/verification.py:1239`): `verified: true`, `status: VERIFIED`, matched genuine invalidation criterion `"The code does not implement explicit race condition protection for cache directory creation"`. Its reason argued lock protection, covering the title at 1.0. `_without_self_refutation` withdrew the invalidation because `_reason_confirms` returned `True`, causing `_verdict_status` to see only confirmation and report the finding as `VERIFIED` with `citation_line=1239`.
- **Finding 1** (`verification.py:1221`): matched a genuine invalidation criterion (`"Path.resolve() normalizes paths to prevent directory traversal"`), had `verified: true`, and because its reason held a negation word ("not"), invalidation was not withdrawn; it ended `UNVERIFIED` with `verifier-inconclusive` and retained `citation_line=1221`.

### Mechanism & Remediation
1. **Self-Refutation Scope**:
   - `_without_self_refutation` now checks `_is_confirmed_verdict(item)`. A verdict confirming its finding (`verified: true` or status `VERIFIED`) that matches an invalidation criterion judged genuine by `_restates_the_finding` is never withdrawn by `_reason_confirms`.
   - The self-refutation withdrawal still applies to a verdict that only refutes.
   - When a confirmation's matched invalidation criteria all restate the finding, the invalidation is withdrawn and the confirmation stands as `VERIFIED`.
2. **Contradiction Note & Inconclusive Separation**:
   - `_verdict_status` now tracks whether a verdict both confirmed and refuted (`contradicted=True`).
   - Every contradictory verdict (`status_val == "UNVERIFIED"`, `contradicted=True`) receives `CONST_VERIFIER_CONTRADICTION` (`"verifier-contradiction"`), clearing `citation_line = None`, `verified_by = None`, and `verified_at = None`.
   - `CONST_VERIFIER_INCONCLUSIVE` remains strictly reserved for verdicts that neither confirmed, refuted, nor found a valid mitigation. `_no_verdict_note`'s docstring is updated accordingly.
3. **Offline Golden & Invariant Tests**:
   - Offline tests in `tests/test_verdict_writers.py` cover `llm_acc69d97` findings (`:1221` and `:1239`), the swapped-criteria fixture with criteria polarized the safe way, unchanged self-refutation (`S10` pricing), unchanged inconclusive (`S10` services.yaml), confirmation with all-restating criteria staying `VERIFIED`, and `_unverified_note_counts` tallying `verifier-contradiction`.

---

## 2. Acceptance Criteria

- [x] A verdict confirming its finding (`verified: true` or status `VERIFIED`) and matching an invalidation criterion judged genuine never ends `VERIFIED`, regardless of whether the reason repeats the title or confirms the claim.
- [x] It ends `UNVERIFIED` and reportable with `verifier-contradiction`, clearing `verified_by`, `verified_at`, and `citation_line`.
- [x] The self-refutation withdrawal still applies to a verdict that only refutes.
- [x] Every verdict that both confirms and refutes gets `verifier-contradiction` instead of `verifier-inconclusive`.
- [x] `verifier-inconclusive` stays for verdicts that neither confirmed, refuted, nor mitigated, with updated `_no_verdict_note` docstring.
- [x] Offline golden tests added covering `llm_acc69d97` and S10's two findings (`:1221` and `:1239`), plus the swapped-criteria fixture.
- [x] Unit tests verify unchanged behavior: S10 pricing (`verifier-self-refutation`), S10 services.yaml (`verifier-inconclusive`), and confirmation with all-restating criteria (`VERIFIED`).
- [x] `_unverified_note_counts` tallies `verifier-contradiction`.
- [x] Replay across cached verifier replies in `.data/reviews/*/candidates.json` documented:
  - 48 findings that previously both confirmed and refuted had ended `verifier-inconclusive`; under the new logic, all such contradictory verdicts correctly receive `verifier-contradiction`.
  - In S10 (`20261003-034353`), `llm_acc69d97`:
    - Finding 1 (`verification.py:1221`): originally ended `UNVERIFIED verifier-inconclusive cit=1221`. Under new logic: `UNVERIFIED verifier-contradiction cit=None`.
    - Finding 2 (`verification.py:1239`): originally ended `VERIFIED llm None cit=1239`. Under new logic: `UNVERIFIED verifier-contradiction cit=None`.
- [x] All tests run offline, without network or LLM calls, passing within fast execution budgets.
- [x] Changelog fragment `changelog.d/1059.md` authored under `### Fixed`.
- [x] `uv run devops ci` passes with 100% green checks.

---

## 3. Deliverables

- [x] `src/devops_cli/ai/review/verification.py`: Scope `_without_self_refutation` to avoid withdrawing genuine refutations on confirming verdicts; emit `CONST_VERIFIER_CONTRADICTION` on contradictory verdicts; clear `citation_line = None`.
- [x] `tests/test_verdict_writers.py`: Golden tests for `llm_acc69d97`, swapped-criteria fixture, regression tests for unchanged behaviors, and note count verification.
- [x] `changelog.d/1059.md`: Changelog entry.
- [x] `docs/agent/tasks/task-1059-contradictory-verdict-unverified.md`: Task documentation.
