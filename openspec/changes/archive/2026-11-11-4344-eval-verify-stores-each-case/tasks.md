# Tasks

## 1. Store each case when it ends

Kind: behavior.

- [x] 1.1 Write failing tests: a stop in the third case keeps the two cases that ended; the report file lists the first case with its findings while the second case runs; rejected credentials in the second case keep the first case in the file.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py`
- [x] 1.2 Score the run from the outcome of each case (`verify_score`), give each case to the caller from a `CaseLifecycle` hook of `pydantic_evals`, and write the report with `write_text_file` at the start and after each case. Delete the evaluator `Recall` and `_recall_scores`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py`

## 2. Resume a stored report

Kind: behavior.

- [x] 2.1 Write failing tests: a resume runs only the failed and the missing cases and updates the same file; a resume with a smaller selection keeps the cases of the report; a report of another model, a report with a case that the set lacks, and a file that is not a report exit 1 with no model call; the dry run of a resume lists only the cases that would run.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py`
- [x] 2.2 Add `--resume`, `resumed_outcomes` and the `done` argument of `evaluate_cases`, with the help text and the messages. Regenerate the command documentation with `devops docs generate --sync-readme`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py`

## 3. Documents

Kind: documents.

- [x] 3.1 Describe the stored file and `--resume` in "Measure the verification pass" of `docs/ROADMAP_WORKFLOW.md`.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
