# Tasks: #4131

- [x] 1. Add marks support to `ReturnPlan` and `apply_return`
  - [x] 1.1 In `src/devops_cli/roadmap/return_item.py`, add `marks` field to `ReturnPlan` dataclass.
  - [x] 1.2 In `src/devops_cli/roadmap/return_item.py`, update `plan_return` to accept optional `marks`.
  - [x] 1.3 In `src/devops_cli/roadmap/return_item.py`, update `apply_return` to pass `marks=plan.marks` to `write_status`.
  - [x] 1.4 In `tests/roadmap/test_roadmap_return.py`, test that `plan_return` and `apply_return` preserve `marks`.
- [x] 2. Route stage return writers through `apply_return`
  - [x] 2.1 In `src/devops_cli/roadmap/stage/stage.py`, update `_return_premise`, `_return_blocked`, `_return_plan_defects`, and `_reject_plan` to call `apply_return`.
  - [x] 2.2 In `src/devops_cli/roadmap/stage/stage_job.py`, update `_return_for_split` to call `apply_return`.
  - [x] 2.3 In `tests/roadmap/stage/test_roadmap_stage_item_writes.py`, add tests proving stage returns call `apply_return`.
- [x] 3. Quality gates and archive
  - [x] 3.1 Run `uv run devops ci test` on affected test suites.
  - [x] 3.2 Run `uv run devops openspec check` and verify 0 problems.
  - [x] 3.3 Archive change with `devops openspec archive`.
