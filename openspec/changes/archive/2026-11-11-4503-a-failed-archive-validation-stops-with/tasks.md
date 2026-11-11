# Tasks

## 1. A spec that the archive validation refuses is a plan defect

Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/failure.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`.

- [x] 1.1 Add a case to `tests/roadmap/implement/test_roadmap_implement_job.py`: the archive moves the change folder and exits 1 with the output of #3462, and the item stops at the archive with `implement.failure` `plan_defect` and the action left `amend`. It fails on the base. Make the case of an archive that keeps the folder assert the class `ci_infra`.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`
- [x] 1.2 Make `_finish_change` pass `plan_defect` on the stop when the archive exits 1 after it moved the change folder into the archive
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`

## 2. Documents

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 Add the refused spec after the archive to the causes of `plan_defect` in the class table of `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: An archive that moved the change folder and then exited 1 stops the item with the class `plan_defect` and the action left `amend`; an archive that keeps the folder keeps its class.
- Group 2: The class table names the new cause of `plan_defect`.
