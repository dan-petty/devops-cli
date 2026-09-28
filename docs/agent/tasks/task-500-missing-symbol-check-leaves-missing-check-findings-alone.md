# Task 500: Missing-Symbol Check Leaves "Missing Check" Findings Alone

**Issue**: [#500](https://github.com/dan-petty/devops-cli/issues/500)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

The deterministic check for false "symbol not defined" claims (`_check_missing_symbol_hallucination`)
ran on any finding containing the word "missing", then invalidated it if a symbol it named existed.
A finding about a missing check always names the function lacking it, so real defects were
invalidated without a model, and `auto_record_invalidated_finding` taught them to the
hallucinations catalog.

### Key Deliverables Completed:

- [x] **Claims, not keywords**: the check runs only on findings that claim a name does not exist:
  - an `ImportError`, `NameError` or `ModuleNotFoundError`;
  - "is not defined", "is undefined" (but not "undefined behaviour"), "not defined in",
    "does not define/export", "cannot be imported";
  - "missing import" or "missing symbol";
  - "missing `name` variable" or "missing _name import", where the name must look like code
    (backticked or containing an underscore).

  "Missing inheritance depth limit in load_policy" no longer qualifies, so it is neither
  invalidated nor recorded into the catalog.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_verification.py`:
    - four real "missing protection" findings survive against a module that defines every
      function they name;
    - four claims that a defined name is undefined or unimportable are still invalidated;
    - the existing cross-module ImportError case still passes.

    With the claim check forced off, the tests that expect an invalidation fail.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

**Replay.** The #415 corpus review had 9 candidates invalidated by this check. None claimed a
symbol was undefined. They are "missing path-traversal validation", "missing error handling",
"missing inheritance depth limit" and similar, and 5 describe injected defects. Replayed through
the new check, all 9 are left for the verifier.

**Live.** The same corpus (seed 1, confirmed identical to the #415 run) was reviewed again with the
fix:

| | Before (#415 run) | After |
| :--- | ---: | ---: |
| Candidates | 68 | 58 |
| Invalidated by the missing-symbol check | 9 | 0 |
| Invalidated by the verifier model | 42 | 38 |
| Injections found | 8 (1 false match) | 7 |
| Injections still reported | 1 | 1 |

The deterministic misfire is gone, but recall after verification did not move. The verifier model
now drops what the check used to, for example "Remote backup directory created with
world-writable permissions" and "Insecure directory permissions when creating known_hosts
directory". Measuring that by model is #475.
