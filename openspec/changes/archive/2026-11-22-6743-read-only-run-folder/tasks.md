# Tasks

## 1. Behavior

- [x] 1.1 Run each publish on a read-only run folder
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_phases.py tests/roadmap/steps/test_roadmap_step_fix_conflict.py tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`
- [x] 1.2 End a left-out item with its reason, and show the dry run of each shape
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_implement_phases.py tests/commands/k8s/test_k8s_run_job.py tests/roadmap/implement/test_roadmap_implement_outside.py`

## 2. Documents

- [x] 2.1 Name the worktree and the home in the disk texts
  - Verification: `$ uv run devops openspec check`
