# Design

## Context

`_execute_due_rows` runs the due rows of a lane one after the other. `_count_job` counts each row that ends in the counter `devops_cli_service_jobs_total` of the `/metrics` path (`GLOBAL_METRICS`). The OTLP metrics go the other way, through `emit()`. The new histogram uses the OTLP way, as the issue asks.

## Decisions

- **Time `row.runner(...)` only, with `clock.monotonic()`.** The clock seam is the project convention (#1320), and the test fixture `clock` moves it, so a test sets the seconds of a row with no sleep. `time.monotonic` does not jump with the wall clock.
- **Send the sample once the result is known.** The success path sends it after the runner returns, with `success`. The `except Exception` path sends it with `_failed_result(exc)` and then handles the error as before. The change swallows no error.
- **Send no sample for a clone failure.** The row never reaches its runner. The job counter still counts it as an error.
- **Send the sample in a run with no lane.** The histogram has no label `lane`, so a lane is not needed. `emit()` is OTLP and works in a short-lived process.
- **Add no zero series at start.** A histogram has no zero point, and `counter_series.py` primes counters only.
- **Declare the instrument with the unit `s`.** Other duration histograms use `s`, and the generated document lists it.
- **Add the requirement to `metric-instruments`.** That capability holds the declared instruments and the rule about the label `job`.

## Rejected Alternatives

- **Add a label `row` to `devops_cli_service_job_seconds_total`.** That counter is on the `/metrics` path and counts one lane round, and the issue asks for a histogram with the labels `repo`, `row` and `result` through `emit()`. A counter gives no per-round distribution, only a mean.
- **Time the whole body of the `try` block.** It would include `ensure_checkout`, so the clone of the first row of a lane would count as the seconds of that row. Evidence: `ensure_checkout` runs inside the same `try` block before the runner.
- **Time a scoped update too.** The issue names `_execute_due_rows`. A scoped update is the fast webhook path of the `intake` row and is not a round of the table.
