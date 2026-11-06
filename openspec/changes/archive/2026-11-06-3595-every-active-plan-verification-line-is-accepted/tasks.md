# Tasks

## 1. Hold every active plan to the grammar of the step

Reads: `tests/invariants/test_change_folders.py`, `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/step_files.py`, `openspec/changes/2610-devops-k8s-image-pins-resolves-with/tasks.md`, `openspec/changes/3187-group-the-job-modules-in-subpackages/tasks.md`. Changes: `tests/invariants/test_change_folders.py`, `openspec/changes/2610-devops-k8s-image-pins-resolves-with/tasks.md`, `openspec/changes/3187-group-the-job-modules-in-subpackages/tasks.md`.

- [x] 1.1 In `tests/invariants/test_change_folders.py`, add a function that returns one problem for each refused code span of a `Verification:` line in the active plans of a changes directory, and add the test `test_every_verification_line_of_an_active_plan_is_accepted_by_the_step` over the repository. A problem names the path of the `tasks.md`, the line and the command. Add cases for a refused first span, a refused second span of one task, an archived plan that the test skips, two active plans that it reads, and a negative search with word boundaries
  - Verification: `uv run devops ci test tests/invariants/test_change_folders.py` fails on the base
- [x] 1.2 Rewrite the refused `Verification:` lines of the plans of 2610 and 3187 in the grammar of the step, as `design.md` says
  - Verification: `uv run devops ci test tests/invariants/test_change_folders.py` passes

## 2. Archive the change

Reads: nothing. Changes: `openspec/changes/3595-every-active-plan-verification-line-is-accepted` (moved by the archive command).

- [x] 2.1 Archive the change
  - Verification: `uv run devops openspec archive 3595-every-active-plan-verification-line-is-accepted` and `uv run devops openspec check`
