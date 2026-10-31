# Tasks

## 1. Rule 11

- [x] Add the check of the open issues and the comment on a match to rule 11 of `AGENTS.md`, within the cap of 6,500 characters
  - Verification: `uv run pytest tests/invariants/test_agents_md_claims.py -n 0`
- [x] Name the search call and the comment in `docs/ROUTINE_TASKS.md`, item 6
  - Verification: `git diff docs/ROUTINE_TASKS.md` and the search command runs with `devops gh api`

## 2. Verification

- [x] Run the full CI quality checks
  - Verification: `uv run devops ci`
