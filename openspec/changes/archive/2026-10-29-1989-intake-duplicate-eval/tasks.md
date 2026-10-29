# Tasks

## 1. The evaluation set is package data

- [x] Move the set to `src/devops_cli/roadmap/intake_duplicate_cases.json`, make `answer` optional, and add the eight wrong folds of 2026-10-24; point the replay tests of #1755 at the new file and the cases that hold an answer
  - Verification: `uv run pytest tests/test_roadmap_intake.py`

## 2. `devops roadmap intake-eval`

- [x] Add failing tests: the set loads with 16 named cases of both verdicts; a run over the model fake prints the table, the agreement count, the precision, the recall and the false duplicates; a failed case is shown with its error and the command exits 1; a checkout with no labels file stops before any model call; the dry run lists 16 calls and makes none
  - Verification: `uv run pytest tests/test_roadmap_duplicate_eval.py`
- [x] Add `roadmap/duplicate_eval.py` (the cases, the task over `intake_candidate`, the pydantic-evals dataset and the score) and the command, its help and its messages
  - Verification: `uv run pytest tests/test_roadmap_duplicate_eval.py tests/test_roadmap_intake.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1989-intake-duplicate-eval`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
