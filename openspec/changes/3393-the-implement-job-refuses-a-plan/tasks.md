# Tasks

## 1. Read the plan of an item and refuse it when the check finds a problem

Reads: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_job.py`.

- [ ] 1.1 Add to `tests/roadmap/test_roadmap_implement_job.py` a test that a Staged item whose branch plan holds the placeholder task `1.1 x` gets no target and a reason with the first problem, a test that a Planned item whose default-branch plan holds the placeholder gets no target and no branch, a test that a plan which passes the check gets a target, a test that a plan the reader cannot parse gets no target and a reason that names the file, and a test that a plan with two problems reports the first problem only
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [ ] 1.2 Move `_head_files`, `_read_files`, `_change_root` and `_base_specs` from `src/devops_cli/roadmap/plan_check.py` to `src/devops_cli/roadmap/plan_read.py` as the public `files_at`, `file_texts_at`, `change_root` and `base_specs_at`, and call them from `plan_check`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py tests/roadmap/test_roadmap_plan_check.py` passes
- [ ] 1.3 Add one function in `src/devops_cli/roadmap/implement.py` that reads the change folder at the revision of an item with `files_at`, `change_root` and `file_texts_at`, builds the `StageProposal` with `read_change`, and calls `check_proposal` with the base facts of `base_specs_at`, the item body and a `StagedTree` of the revision. Call it from `_Judge.judge` for a Staged and a Planned item, before `_planned_target` makes a branch, and return the first problem or the read reason as the reason of a `LeftOut`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes

## 2. Name the plan problem in the page of the implement job

Reads: `docs/roadmap/implement.md`. Changes: `docs/roadmap/implement.md`.

- [ ] 2.1 Add the plan check to the list of reasons that the implement job leaves an item out, in the page that the help of `devops roadmap implement` names, so a person reads why an item with a refused plan waits
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
