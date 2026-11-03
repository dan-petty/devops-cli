# Tasks

## 1. Refuse a plan that leaves out a caller of a changed function

Reads: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_paths.py`.

- [ ] 1.1 Write `test_a_plan_that_leaves_out_a_caller_is_refused` in `tests/roadmap/test_roadmap_stage_paths.py`. It makes a checkout where src/a.py and src/b.py call `check_proposal`, and asserts that a plan whose `changes` list omits src/b.py gets a problem that names `check_proposal` and src/b.py
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` fails on the base
- [ ] 1.2 Read the function name from each task text that adds a parameter, search the callers with `git grep` on the checkout of `StagedTree`, and return one problem for each caller file that `changes` leaves out. Skip a tree with no checkout
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
