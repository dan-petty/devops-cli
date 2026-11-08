# Tasks

## 1. Send the seconds of each row

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/core/clock.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/run.py`.

- [x] 1.1 Add `tests/telemetry/test_roadmap_row_seconds.py` with the cases of the spec. Run it and see it fail on the base
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_row_seconds.py` fails on the base
- [x] 1.2 Declare `ROADMAP_ROW_SECONDS` (histogram, unit `s`) in `src/devops_cli/telemetry/instruments.py` and add it to `INSTRUMENTS` and `__all__`. In `_execute_due_rows`, read `clock.monotonic()` before `row.runner(...)` and call `emit(ROADMAP_ROW_SECONDS, seconds, {"repo": repo, "row": row.name, "result": result})` on the success path and in the `except Exception` path, with the result of `_count_job`
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_row_seconds.py tests/telemetry/test_telemetry_instruments.py tests/roadmap/test_roadmap_run_job_counts.py` passes

## 2. Document the series

Reads: `docs/TELEMETRY.md`, `src/devops_cli/docs/generator.py`. Changes: `docs/TELEMETRY.md`.

- [x] 2.1 Run `uv run devops docs generate` so that `docs/TELEMETRY.md` lists the histogram with its labels and its series count
  - Verification: `$ grep -q devops_cli_roadmap_row_seconds docs/TELEMETRY.md` exits 0

## Criteria

- Group 1: A round emits one sample for each row that ran, with its `row` and `result`. A row that is not due or that the ledger suspends adds none. A row that raises adds a sample with the result `error` or `stopped`.
- Group 2: `docs/TELEMETRY.md` lists `devops_cli_roadmap_row_seconds`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
