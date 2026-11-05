# Tasks

## 1. Read the plan of an item and refuse it when the check finds a problem

Reads: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/lang/en/messages.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/lang/en/messages.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_implement_plan_reason.py`.

- [x] 1.1 Add to `tests/roadmap/test_roadmap_implement_job.py` a test that a Staged item whose branch plan holds the placeholder task `1.1 x` gets no target and a reason with the first problem, a test that a Planned item whose default-branch plan holds the placeholder gets no target and no branch, a test that a plan which passes the check gets a target, a test that a plan the reader cannot parse gets no target and a reason that names the file, and a test that a plan with two problems reports the first problem only. Give the test world of `tests/support/roadmap_implement.py` a plan that the gates accept.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [x] 1.2 Move `tree_files`, `files_at`, `_change_root` and `specs_at` from `src/devops_cli/roadmap/plan_check.py` to `src/devops_cli/roadmap/plan_read.py` as the public `tree_files`, `files_at`, `change_root` and `specs_at`, and call them from `plan_check` and `plan_recheck`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py tests/roadmap/test_roadmap_plan_check.py` passes
- [x] 1.3 Add one function in `src/devops_cli/roadmap/implement.py` that reads the change folder at the revision of an item with `tree_files`, `change_root` and `files_at`, builds the `StageProposal` with `read_change`, and calls `check_proposal` with the base facts of `specs_at` at `origin/<default>`, the item body and a `StagedTree` of the revision. Cache the base facts for each `plan_implement` call. Call it from `_Judge.judge` for a Staged and a Planned item, before `_planned_target` makes a branch, and return the first problem or the read reason as the reason of a `LeftOut`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes
- [x] 1.4 Add a test to `tests/roadmap/test_roadmap_implement_plan_reason.py` that explain and the report name the first problem of a refused Staged plan
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_plan_reason.py` fails on the base

## 2. Name the plan problem in the page of the implement job

Reads: `docs/roadmap/implement.md`. Changes: `docs/roadmap/implement.md`.

- [x] 2.1 Add the plan check to the list of reasons that the implement job leaves an item out, in the page that the help of `devops roadmap implement` names, so a person reads why an item with a refused plan waits
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
