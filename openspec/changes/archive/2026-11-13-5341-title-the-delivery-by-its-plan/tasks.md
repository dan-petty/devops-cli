# Tasks

## 1. The delivery title takes the summary of the plan

Kind: behavior. Reads: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/stage/test_roadmap_stage_title.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/support/roadmap_implement.py`.

- [x] 1.1 Write the failing tests: `test_the_delivery_title_names_the_change_of_the_plan_and_not_the_goal_of_the_issue` with the real titles and plan subjects of #5336, #5324, #5355 and #4980, `test_a_subject_that_is_no_plan_title_of_the_item_gives_no_summary` and `test_no_plan_summary_keeps_the_summary_of_the_issue` in `tests/roadmap/stage/test_roadmap_stage_title.py`. Add the fixture `plan_subject` and the option `subject` of `push_staged_branch` and `merge_plan` to `tests/support/roadmap_implement.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_title.py`
- [x] 1.2 Write the failing tests `test_the_title_of_a_staged_item_names_the_change_of_its_plan`, `test_the_title_of_a_planned_item_names_the_change_of_its_merged_plan` and `test_a_plan_summary_that_the_form_refuses_gives_way_to_the_summary_of_the_issue` in `tests/roadmap/implement/test_roadmap_implement_job.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`
- [x] 1.3 Add `plan_summary` and the argument `summary` of `delivery_title` to `src/devops_cli/roadmap/stage/stage_change.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_title.py`
- [x] 1.4 Add `_plan_summary` to `src/devops_cli/roadmap/implement/implement_run.py`, and make `_delivery_title` use the summary of the plan when the form accepts the title.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`

## 2. Documents

Kind: documents. Changes: `docs/roadmap/implement.md`.

- [x] 2.1 Describe the title of the delivery pull request in step 6 of `docs/roadmap/implement.md`.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- A Conventional Commit type from the changed paths of the plan stays in #4127.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
