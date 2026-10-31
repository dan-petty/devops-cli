# Tasks

## 1. Amend ADR 0007

- [x] Record the owner decision of 2026-10-24 in ADR 0007, and name the removed allowances
  - Verification: `rg -n "2026-10-24" docs/adr/0007-tests-double-only-process-edges.md`

## 2. Update docs/TESTING.md

- [x] Remove the Live test definition and remove programs from the Real list in docs/TESTING.md
  - Verification: `rg -n "Live test" docs/TESTING.md` returns no matches
- [x] Specify that real children stay only in the process runner contract suite, route other tools to recorded contract suites or devops ci rows, and name the bwrap suite as opt-in
  - Verification: `rg -n "contract suite" docs/TESTING.md`

## 3. Verification

- [x] Run invariant checks and full CI checks
  - Verification: `uv run pytest tests/invariants/test_agents_md_claims.py` and `uv run devops ci`
