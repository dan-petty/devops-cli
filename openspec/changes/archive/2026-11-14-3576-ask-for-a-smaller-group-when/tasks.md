# Tasks

## 1. Name the group in the no-change stop

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_trace.py`. Changes: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_step_failure_class.py`, `tests/roadmap/implement/test_roadmap_implement_step_attempts.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_strays.py`.

- [x] 1.1 Format the no-change reason with the group number and title and the request for a smaller replacement
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py` passes
- [x] 1.2 Add the case that the trace holds `plan_defect` for the no-change group and no class for a changed group
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py` passes

## 2. Replace a group with a smaller one

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_amend.py`, `src/devops_cli/roadmap/step_files.py`. Changes: `src/devops_cli/roadmap/implement/implement_amend.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`.

- [x] 2.1 Accept the kind `group`, apply a replacement with fewer tasks, and refuse one that has as many tasks, changes the number or names a new path
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_amend.py` passes

## 3. Run the gates

Kind: other. Reads: `tests/roadmap/implement/`. Changes: none.

- [x] 3.1 Run the gate of the branch
  - Verification: `$ uv run devops ci test tests/roadmap/implement` passes
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck` passes
