# Task 514: Hallucinations Catalog Learns From Unreliable Invalidations and Never Forgets

**Issue**: [#514](https://github.com/dan-petty/devops-cli/issues/514)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

From the #509 audit. The common hallucinations catalog learned from:
- LLM verdicts;
- weak deterministic checks;
- evaluation replays.

Learning added each finding's words to builtin entries and persisted the copy, which then
shadowed the shipped entry and its later fixes. Nothing listed or removed what it learned. Some
categories' ground truth only checked that the file parsed. The legacy persona path showed
learned entries to reviewers as "disproved".

### Key Deliverables Completed:

- [x] **Only evidence teaches**:
  - A model's invalidation no longer records into the catalog; it is the judgement under test.
  - Deterministic checks with ground truth still teach (a parser, the AST, a type check, a catalog
    match that passed its own ground truth), and so does a person's `devops review verify`.
  - `catalog_learning_disabled()` stops evaluation replays (`prompt_eval`) from teaching.
- [x] **Builtin entries are fixed**:
  - A finding matching a builtin entry leaves it unchanged, and a builtin id is never persisted.
  - A learned copy of a builtin id already in a ledger is ignored at load, so the shipped entry
    and its fixes apply.
  - A malformed ledger record is skipped on its own.
- [x] **Learned entries can be managed**: `devops review hallucinations list [--learned] [--json]`,
  and `devops review hallucinations remove <id>... | --all-learned`. Builtin entries cannot be
  removed.
- [x] **Ground truth checks the claim**:

  | Category | Change |
  | :--- | :--- |
  | Syntax grammar | Holds only for a syntax-error claim against a file that parses |
  | Symbol and header entries | Defer to their deterministic checks, which ran first with the claim's own evidence |
  | Mutable defaults | Look for `default_factory` at the cited lines, not anywhere in the module |
  | CWE-400 | Steps aside when the finding describes user, uploaded, request or other untrusted input |

- [x] **Reviewers see curated entries only**: the legacy "Previously Recorded False Positives"
  block lists builtin entries, never learned ones, which may be real defects verification got
  wrong.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_hallucination_catalog_learning.py`:
    - a model invalidation records nothing;
    - a disabled block learns nothing;
    - a persisted builtin copy is ignored;
    - each ground-truth rule;
    - the prompt block excludes learned entries;
    - list and remove, with builtins refused;
    - four real defects from the audit that the builtin catalog must not invalidate. The CWE-400
      upload case fails without the untrusted-input rule.
  - Existing tests that expected learning to widen a builtin entry, or catalog ground truth to
    confirm symbol and header claims, now assert the new rules.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

The ledger still lives under the repository of the current directory rather than the review
target's. With learning limited to deterministic evidence, a stray entry is now rare and can be
listed and removed.
