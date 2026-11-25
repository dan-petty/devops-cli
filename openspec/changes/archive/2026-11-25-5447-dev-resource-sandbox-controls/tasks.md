# Tasks

## 1. Behavior

- [x] 1.1 Add failing invariant tests for the `SECURITY.md` dedicated resources and sandboxes section, control table validation (including empty table, missing fields, and `YYYY-MM-DD` review date), and guideline links in `tests/invariants/test_agents_md.py` and `tests/invariants/test_guidelines.py`
  - Verification: `$ uv run pytest tests/invariants/test_agents_md.py tests/invariants/test_guidelines.py`

## 2. Documents

- [x] 2.1 Update `SECURITY.md` (`## Dedicated Development Resources and Sandboxes`), `docs/guidelines/agentic-jobs.md` (tuning loop step 3), and `docs/guidelines/sre.md` (Table 1) and verify all checks pass
  - Verification: `$ uv run pytest tests/invariants/test_agents_md.py tests/invariants/test_guidelines.py tests/invariants/test_committed_addresses.py && uv run devops docs check`
