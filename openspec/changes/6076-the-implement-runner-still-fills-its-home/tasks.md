# Tasks

## 1. The strength check

Kind: behavior. Changes: `src/devops_cli/roadmap/implement/implement_strength.py`, `src/devops_cli/ci/mutate.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_strength.py`.

- [x] 1.1 Write the failing tests: a scoped run under the floor of the whole suite passes on its changed lines, and a change with no source file runs no mutation run and no coverage run
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py`
- [x] 1.2 Give the coverage report no floor, and run only the assertion scan for a change with no Python file under `src/`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py`

## 2. The end of a step and the disk use line

Kind: behavior. Changes: `src/devops_cli/roadmap/implement/implement_disk.py` (new), `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/commands.py`, `tests/roadmap/implement/test_roadmap_implement_disk.py` (new), `tests/roadmap/implement/test_roadmap_implement_strays.py`.

- [x] 2.1 Write the failing tests: the disk use line in a runner Job, no line outside it, the line before the removal, the removal at the end of a done and of a stopped step, and the line of a stop
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_disk.py`
- [x] 2.2 Add `implement_disk.py`, call `end_step` at the end of `run_step` and `log_disk_use` in the stop of the job
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_disk.py tests/roadmap/implement/test_roadmap_implement_strays.py`

## 3. Documents

Kind: other. Changes: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`.

- [x] 3.1 Describe the coverage floor, the change with no source file, the end of a step and the disk use line
  - Verification: `$ uv run devops ci docs`
