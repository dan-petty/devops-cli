# Tasks

## 1. Write the rule for a finding with no fix

Reads: `AGENTS.md`, `docs/ROUTINE_TASKS.md`. Changes: `SECURITY.md`, `AGENTS.md`, `docs/ROUTINE_TASKS.md`.

- [x] 1.1 In `SECURITY.md`, add the section "A Finding with No Fix" before "Reporting a Vulnerability"
  - Verification: `uv run devops docs check`
- [x] 1.2 In `AGENTS.md`, add to rule 5 one clause that links the section, and keep the file inside its character budget
  - Verification: `uv run devops ci test tests/invariants/test_agents_md_claims.py`
- [x] 1.3 In `docs/ROUTINE_TASKS.md`, add the matrix row and the Cadence D bullet that name the renewal and link the section
  - Verification: `uv run devops docs check`
- [x] 1.4 Check the change folder
  - Verification: `uv run devops openspec check`
