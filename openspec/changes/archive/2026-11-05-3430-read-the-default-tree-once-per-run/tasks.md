# Tasks

## 1. List the default tree once for each run

Reads: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/plan_recheck.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/plan_read.py`, `tests/roadmap/test_roadmap_implement_job.py`.

- [x] 1.1 Add a test in `tests/roadmap/test_roadmap_implement_job.py` that two Planned items give one listing of `origin/main`. Run it first and see it fail on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [x] 1.2 Add a test in that file: two Planned items give one read of each base spec file
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes on the base
- [x] 1.3 Add a test in that file: two Staged items give one listing for each branch
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes on the base
- [x] 1.4 Add a test in that file: three items get the same decisions as a run over each item alone
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes on the base
- [x] 1.5 Add a test in that file: a default tree that git cannot list leaves each Planned item out. The run does not end
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes on the base
- [x] 1.6 Add the optional `files` argument to `specs_at` in `src/devops_cli/roadmap/plan_read.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py tests/roadmap/test_roadmap_plan_check.py tests/roadmap/test_roadmap_plan_recheck.py` passes
- [x] 1.7 Add `_default_files` and `_tree` to `_Judge` in `src/devops_cli/roadmap/implement.py`. Read the tree of a revision with `_tree` in `_plan_reason`. Give `_default_files` to `specs_at` in `_base_facts`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes

## 2. Say in the page of the implement job that a run reads the default tree once

Reads: `docs/roadmap/implement.md`. Changes: `docs/roadmap/implement.md`.

- [x] 2.1 Add two sentences to the paragraph about the plan check in `docs/roadmap/implement.md`. The first says that a run lists the default branch and reads its base specs one time. The second says that the check lists the branch of each Staged item for that item
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
