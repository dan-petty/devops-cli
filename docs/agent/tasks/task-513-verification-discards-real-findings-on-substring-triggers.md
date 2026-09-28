# Task 513: Verification Discards Real Findings on Substring Triggers and Malformed Verdicts

**Issue**: [#513](https://github.com/dan-petty/devops-cli/issues/513)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/bug`, `scope/review`, `priority/p0-critical`

---

## 1. Description & Objectives

From the #509 audit: deterministic verification checks fired on substrings of a finding's
wording, and LLM verdicts were read so that malformed, uncertain or misbound verdicts discarded
real findings.

### Key Deliverables Completed:

- [x] **Verdicts read as meant** (`_apply_single_finding_verification`):
  - The strings "false", "no" and "none" are not true.
  - `invalidated_criteria_matched: "none"` is no longer iterated character by character.
  - The `status` and `invalidated` fields the prompt asks for are honoured.
  - A verdict that both confirms and refutes a finding leaves it unverified and reported.
  - So does `verified: false` without invalidating evidence, as with no verdict at all.
- [x] **Verdicts bind by title** (`_bind_verdicts_to_findings`, `_is_matching_finding`): a shared
  location no longer binds a verdict, and a verdict with no title binds to nothing, where it used
  to take the first unclaimed finding. The location breaks ties between title matches. The same
  matcher drives the legacy reconcile step.
- [x] **Each deterministic check fires on its own claim**:

  | Check | Change |
  | :--- | :--- |
  | Syntax | An actual syntax-error claim, not the word "syntax" ("f-string syntax", "bare `except` clause") |
  | Line past EOF | The miscounted line is dropped from the location; the finding is kept, not invalidated |
  | `Path.resolve()` | A `resolve(strict=True)` claim, which is true, is left alone |
  | Auth header | The header must be set near the cited lines, not anywhere in the module |
  | Runtime floor | Read from the reviewed project's `pyproject.toml`, not devops-cli's |
  | Health and stream | Whole words: "sse" in "processed", "health" in "healthy" no longer match |
  | Test-fixture secrets | Only an obviously synthetic value; a real password in `tests/` is kept |
  | Uninitialized variable | The innermost function, so a closure missing `nonlocal` is kept |
  | Monologue and praise | Reasoning must open the title; praise wording that is negated ("not properly implemented") is a finding |
  | Redaction marker | A claim that the value behind the marker is a live secret is kept |
  | None dereference | Code `None`/`NoneType`, not English "if none of the roles" |

- [x] **Scope moved**: the verifier prompt's devops-cli assumptions (`mypy --strict`, internal
  connectors, console output) need the target's conventions passed to the verifier, which #515
  adds for persona review too.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_verification.py`:
    - verdict parsing and contradictions;
    - binding at a shared line and without a title;
    - twelve real findings that must survive `_deterministic_pre_verification`, ten of which fail
      on the old code;
    - the runtime floor of a project supporting Python 3.9.
  - Existing tests that asserted an out-of-range line or an empty verdict invalidates or hides a
    finding now assert it is kept.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

The #415 corpus (seed 1, byte-identical to the earlier runs), reviewed with all personas through
the homelab gateway, on this change alone (without #500 or #512):

| | #500 run | This change |
| :--- | ---: | ---: |
| Injections found | 7 | 9 |
| Injections still reported | 1 | 2 |
| Findings reported in all | 7 | 21 |
| Of them unverified, kept because the verdict neither confirmed nor refuted them | 0 | 9 |
| Reported findings beyond the injections | 0 | 15 |

- **Genuine**: "resolve_safe_subpath does not enforce containment, allowing path traversal" was
  reported for the dropped containment guard in `core/repo.py`.
- **Weak**: the `core/paths.py` injection counted as reported through a line match on "Redundant
  traversal checks".

The trade is visible: fewer real findings are discarded, and more findings the verifier did not
confirm reach the report, marked UNVERIFIED. The missing-symbol check still invalidated 9
candidates here because #500 is not in this branch. The verifier model's own invalidations
(39 of 51) remain the largest loss; its prompt is #515 and its per-backend quality is #475.
