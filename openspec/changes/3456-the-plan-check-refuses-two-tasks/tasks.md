# Tasks

## 1. Refuse two plan tasks that state the same work

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/test_roadmap_stage_content.py`, `tests/support/roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_content.py`.

- [x] 1.1 Add to `tests/roadmap/test_roadmap_stage_content.py` a test for a duplicate in one group, a test for a duplicate across two groups, a test for two tasks that share a `Verification:` command, a test for a documentation task that repeats a work text, and a test for work text that differs only in spacing and case; each test builds a `StageProposal` and calls `check_proposal`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` fails on the base
- [x] 1.2 Add `stage_problem_duplicate_task`, `stage_group_one` and `stage_group_two` to the roadmap messages of `src/devops_cli/lang/en/messages.py`. Add a helper in `src/devops_cli/roadmap/stage_change.py` that returns the work text of each task of a group in the order of `_task_texts`: the test, the implementation and the documentation. Normalize each text with `" ".join(text.split()).casefold()`, compare every task of the plan with every later task, and append the formatted problem to `content_problems`. Name both task numbers and the group or groups, and update the docstring of `content_problems`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
