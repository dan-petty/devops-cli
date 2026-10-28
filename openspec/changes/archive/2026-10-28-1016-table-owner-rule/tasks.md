# Tasks

## 1. The documents state the placement rule

- [x] Replace the placement bullet of "Closed Lists and Standard Parsers" and the Constant row of the naming table in `CONTRIBUTING.md`
  - Verification: `git grep -n "constants.py" CONTRIBUTING.md` shows no sentence that puts every table in `config/`
- [x] State the same rule in the matrix row, the flowchart step and step 3 of `docs/ROUTINE_TASKS.md`
  - Verification: `uv run devops docs check`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1016-table-owner-rule`

## Workflow follow-up

- #1025 to #1032 move the single-owner tables of their packages out of `config/`.
