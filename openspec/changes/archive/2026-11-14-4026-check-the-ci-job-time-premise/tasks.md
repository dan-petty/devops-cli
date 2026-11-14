# Tasks

## 1. Read and compare the stated job-time limit

Reads: `src/devops_cli/ci/job_time.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/failure.py`.

Changes: `src/devops_cli/roadmap/stage/stage_time.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_time.py`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 1.1 Write the parse, the verdict and the wiring tests, and watch them fail.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_time.py`
- [x] 1.2 Add the module, the message and the check before the planner call.
  - Verification: `$ uv run devops ci test tests/roadmap/stage`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
