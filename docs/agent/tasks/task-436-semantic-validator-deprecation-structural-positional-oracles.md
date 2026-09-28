# Task 436: Semantic Validator Deprecation & Structural Positional Oracles

**Issue**: [#436](https://github.com/dan-petty/devops-cli/issues/436)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Audits AI review schemas and validators to strip keyword-matching assertions in favor of strict structural schema boundaries and positional enumeration / structural positional oracles.

#### Key Deliverables:
- [x] Centralized review schema and deterministic verification constants in `src/devops_cli/config/constants.py` (`CONST_REVIEW_PROMPT_PLACEHOLDER_BASENAMES`, `CONST_REVIEW_TITLE_FILLER_WORDS`, `CONST_AUTH_HEADER_CLAIM_KEYWORDS`, `CONST_AUTH_HEADER_CODE_PATTERNS`, `CONST_AUTH_DISPATCH_PATTERNS`, `CONST_FIXTURE_CREDENTIAL_KEYWORDS`, `CONST_MASKED_SYNTAX_ERROR_PHRASES`, `CONST_UNINITIALIZED_CLAIM_KEYWORDS`, `CONST_MONOLOGUE_PREFIXES`, `CONST_COMPLIMENT_PHRASES`, `CONST_COMPLIMENT_NEGATIONS`, `CONST_HALLUCINATION_FORBIDDEN_WORDS`).
- [x] Stripped brittle `has_scratchpad_phrase` regex in `canonicalize_finding_location` in favor of strict structural location grammar parsing (`_LOCATION_REGEX`, `_TARGET_LOCATION_REGEX`, `_EMBEDDED_LOCATION_REGEX`), cleanly rejecting malformed non-path text to `""`.
- [x] Added structural positional identifier `finding_id: int | None` with aliases (`id`, `index`) to `Finding` schema in `src/devops_cli/ai/review_schema.py`.
- [x] Implemented structural positional oracle resolution in `_bind_verdicts_to_findings` (`src/devops_cli/ai/review/verification.py`), prioritizing positional `finding_id` to eliminate title-drift and verdict-misbinding vulnerabilities, with seamless identity fallback.
- [x] Updated verification prompt protocol in `src/devops_cli/ai/tasks/verify_finding_system.md` to require returning `finding_id` in verdict arrays.
- [x] Decomposed `_match_verdict_by_positional_oracle` into pure predicate helpers (`_extract_verdict_pos_id`, `_find_by_explicit_finding_id`) to ensure $M \le 6$ and depth $\le 3$.
- [x] Comprehensive unit and integration test coverage in `tests/test_structural_positional_oracles.py` with structural tuple equality assertions.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Verification & Validation Results

- `uv run pytest tests/test_structural_positional_oracles.py -v`: All 11 tests passed.
- `uv run pytest tests/test_review_verification.py -v`: All 84 tests passed.
- `uv run devops scan complexity tests/test_structural_positional_oracles.py`: $M \le 10$, depth $\le 5$ compliant.
- `uv run devops ci`: All 10 Gated CI Quality Gates passing.
