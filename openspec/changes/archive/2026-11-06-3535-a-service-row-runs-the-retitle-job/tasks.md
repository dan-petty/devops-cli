# Tasks

## 1. Run the retitle job as a model-lane row

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/retitle.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/test_roadmap_run.py`, `tests/roadmap/test_roadmap_retitle.py`. Changes: `src/devops_cli/roadmap/run.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/test_roadmap_retitle.py`, `tests/roadmap/test_roadmap_run.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_retitle.py`, write cases for the row: it sits between `refine` and `stage` of `MODEL_LANE_ROWS` and is in `DEFAULT_DUE_TABLE`; it is due on a first run and at 61 minutes but not at 60; it plans with the limit `DEFAULT_ROADMAP_RETITLE_LIMIT` and applies the plan; a round records its success; a default stub table has no `retitle` row
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_retitle.py` fails on the base
- [x] 1.2 In `src/devops_cli/config/defaults.py`, add `DEFAULT_ROADMAP_RETITLE_INTERVAL_MINUTES: int = 61`. In `src/devops_cli/roadmap/run.py`, add `_run_retitle_adapter`, the `retitle` row in `MODEL_LANE_ROWS` and `include_retitle` in `build_stub_table`. Update the row lists in `tests/roadmap/test_roadmap_run.py` and `tests/roadmap/test_roadmap_stage_job.py` that name the model lane rows
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_retitle.py tests/roadmap/test_roadmap_run.py` passes

## 2. Documents

Reads: `CONTEXT.md`, `docs/roadmap/intake.md`. Changes: `CONTEXT.md`, `docs/roadmap/intake.md`.

- [x] 2.1 In `CONTEXT.md` and `docs/roadmap/intake.md`, name the `retitle` row of the model lane and its 61-minute interval
  - Verification: `uv run devops ci docs`

## Criteria

- Group 1: The model lane SHALL hold a row `retitle` after `refine` and before `stage`.
- Group 1: The row SHALL be due on a first run and after 61 minutes.
- Group 1: The row SHALL call `plan_retitle` with `limit=DEFAULT_ROADMAP_RETITLE_LIMIT`, then `apply_retitle`.
- Group 1: `build_stub_table` SHALL omit the row unless asked.
- Group 2: The documents SHALL name the row and its interval.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
