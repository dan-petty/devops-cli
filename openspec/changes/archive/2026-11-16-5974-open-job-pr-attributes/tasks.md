# Tasks

## 1. Behavior

- [x] 1.1 Write a failing test: a pushed branch whose diff changes runtime code, for an item of the type `test`, gets a title whose type ships a release and that the CI title rules accept
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_open.py`
- [x] 1.2 Check the type, the scope, the summary and the body in the open step with `release_title` and `pull_form`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_open.py tests/github/test_release_title.py tests/roadmap/test_roadmap_pull_form.py`
- [x] 1.3 Add the row `open` and the setting `roadmap.open` with the modes `off`, `plan` and `on`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_open_row.py tests/roadmap/test_roadmap_run_due_table.py`

## 2. Documents

- [x] 2.1 Describe the row in `docs/CLUSTER.md`, add the Status History line of ADR 0021, and add the setting to the ConfigMap template
  - Verification: `$ uv run devops ci docs`
