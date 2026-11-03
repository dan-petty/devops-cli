# Tasks

## 1. Refuse a task of one word

Reads: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_change.py`. Changes: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_form.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_form.py`, assert that `form_problems` refuses a bare path, a single word and a lone code span as the `test` of a group and names the group, refuses a bare `implementation` and `documentation`, and accepts a sentence with a verb and an object
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py`
- [x] 1.2 Add `_task_problems` to `src/devops_cli/roadmap/stage_form.py`, call it from `form_problems`, and add `stage_problem_task` to `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py`

## 2. Refuse a repeated word and a repeated number in a title

Reads: `src/devops_cli/roadmap/pull_form.py`. Changes: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_pull_form.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_pull_form.py`, assert that `title_problems` refuses `plan #2950 plan alternatives coverage telemetry` and `plan #2950 Add coverage for #2950`, and accepts `plan #2950 Add alternatives coverage telemetry` and `plan #3200 Refuse placeholder and cut plan text`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_pull_form.py`
- [x] 2.2 Add `_repeat_problems` to `src/devops_cli/roadmap/pull_form.py`, call it from `_summary_problems`, and add `form_title_repeat_word` and `form_title_repeat_number` to `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_pull_form.py`

## Workflow follow-up

- Item 3 of the issue, the content check at the ready mark of a plan, is moved to #3297.
- The stage job calls no form check on `staging_title`, so the new title rule does not guard the staged plan title until #3215 lands.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
