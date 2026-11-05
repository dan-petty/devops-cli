# Tasks

## 1. List the default tree once for each run

Reads: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/plan_recheck.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/plan_read.py`, `tests/roadmap/test_roadmap_implement_job.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_implement_job.py`, add the tests that count the git commands of a run at the process edge: one listing of `origin/main` for two Planned items, one read of each base spec file, one listing for each of two Staged branches, the same target or reason for each of three items as a run that names the item, and a left-out reason when git cannot list the default tree. Run them first and see the first one fail on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [x] 1.2 Add the optional `files` argument to `specs_at` in `src/devops_cli/roadmap/plan_read.py`. Add `_default_files` and `_tree` to `_Judge` in `src/devops_cli/roadmap/implement.py`, read the tree of a revision with `_tree` in `_plan_reason`, and give `_default_files` to `specs_at` in `_base_facts`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_plan_read.py tests/roadmap/test_roadmap_plan_check.py tests/roadmap/test_roadmap_plan_recheck.py` passes

## 2. Say in the page of the implement job that a run reads the default tree once

Reads: `docs/roadmap/implement.md`. Changes: `docs/roadmap/implement.md`.

- [x] 2.1 Add one sentence to the paragraph about the plan check in `docs/roadmap/implement.md`: a run lists the default branch and reads its base specs one time and gives them to the check of every item, and the check lists the branch of each Staged item for that item
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
