# Tasks

## 1. Check the plan title in the stage job

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/pull_form.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_pull_form.py`, `tests/roadmap/test_roadmap_stage_form.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_plan.py`, assert that a reply with the summary `plan the form of a task` goes back to the model once, and a summary with the issue number stops the item on the second reply. In `tests/roadmap/test_roadmap_pull_form.py`, assert the evasions (colon, two spaces, a word before, a hyphen word, a dash, quotes, brackets) and that `add #29501` stays valid. In `tests/roadmap/test_roadmap_stage_form.py`, assert that a code span of three words alone is refused
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`
- [x] 1.2 Call `title_problems` in `_settle` of `src/devops_cli/roadmap/stage.py`, widen `_LEAD` in `src/devops_cli/roadmap/pull_form.py`, and add the summary sentence to `src/devops_cli/ai/tasks/roadmap_stage_change.md`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`

## Workflow follow-up

- #3215 builds the other texts of the jobs with `pull_form`.
- Known limit: the task gate counts words, so a text of two paths passes.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
