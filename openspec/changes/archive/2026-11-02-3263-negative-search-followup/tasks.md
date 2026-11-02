# Tasks

## 1. The agent learns that the step runs a bang command

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`. Changes: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/test_roadmap_implement_shell_refusal.py`, `tests/roadmap/test_roadmap_implement_shell_policy.py`.

- [x] 1.1 Write the tests that the refusal of `! git grep -n x src/` holds the `git grep` form and the sentence that the step runs it, and that the prompt and the table say it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_refusal.py tests/roadmap/test_roadmap_implement_shell_policy.py` fails on the base
- [x] 1.2 Add the row `!` to the refusal table, the sentence to step 5 of the prompt, and the row to the table of `docs/ROADMAP_WORKFLOW.md`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_refusal.py tests/roadmap/test_roadmap_implement_shell_policy.py`

## 2. A search has a limit, a safe reason and one reader

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/config/constants.py`. Changes: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_negative_search.py`, `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 2.1 Write the tests for a fullwidth or accented literal and path, a word of 300000 characters, a word with a NUL byte or a line break, and the reason that the step and the gate share
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_negative_search.py` fails on the base
- [x] 2.2 Add the limit and the escape to the reader, add `read_verification`, call it from `commands_failure`, and replace the three refusal messages with one
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_negative_search.py tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_limit_classes.py tests/roadmap/test_roadmap_stage_form.py`

## 3. Archive

Kind: other.

- [x] 3.1 Archive the change
  - Verification: `uv run devops openspec archive 3263-negative-search-followup` and `uv run devops openspec check`

## Workflow follow-up

- Several names in one negative search (`-e`, repeated), and the plan of #2610 that uses `-E`, are a separate issue that a person files with `devops roadmap intake`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
