# Tasks

## 1. One limit for the summary of a plan title

Kind: behavior. Reads: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_title.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [x] 1.1 Write failing tests: a summary of the most characters that the schema accepts gives a title that `title_problems` accepts, for numbers of 1 to 6 digits; the schema limit is the room that the title leaves for the largest number; a summary that grows past the room with a handle is refused; the prompt names the limit of the schema
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [x] 1.2 Add `ISSUE_NUMBER_DIGITS` and `STAGE_SUMMARY_MAX_CHARS`, use the limit in the field `summary`, add the validator and its message, and change the prompt to 47 characters
  - Verification: `uv run devops ci test tests/roadmap`

## 2. Archive the change

Kind: other. Changes: `openspec/changes/3249-staging-title-limit`, `openspec/specs/roadmap-stage/spec.md`.

- [x] 2.1 Archive the change after every task is ticked
  - Verification: `uv run devops openspec check`

## Workflow follow-up

- `delivery_title` and the "why" of `implement_run.py` still cut text with `...`, and `staging_title` keeps its cut for a number of 7 digits. Issue #3215 removes these cuts.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
