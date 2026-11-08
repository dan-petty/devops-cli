# Design

## Decisions

- **Three rows, one runner each.** The row is the unit that the counter, `schedule.json`, the record of failed rounds and the alert already key on. A row per source gives each source its own result with no new state.
- **Remove the three `except Exception` blocks and wrap nothing.** `_execute_due_rows` already turns a raised error into `result=error`, a failed-round count and a suspension. The readers already raise `ServiceStatusError`. A project metrics error (for example a `TypeError` on a bad milestone count) also reaches the row unchanged; the row then fails with the real error class, which the record of failed rounds keeps as the cause.
- **Put the two status rows last in `STATUS_LANE_ROWS`.** A row waits for the rows before it in the lane. A status page that is slow then delays no other row. The sentences that say `implement` follows `metrics` stay true.
- **`needs_clone=False` for the status rows.** They fetch a public page and read no file. A missing clone then fails `metrics` only.
- **Reuse `DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES`.** The three reads were one call each round at that interval, so no interval changes.
- **No change to `counter_series.py`, the alert or `build_stub_table` logic.** `prime_counter` reads `STATUS_LANE_ROWS`, the alert groups on `row`, and `kept.get(name, True)` keeps unknown rows. Only the docstring of `build_stub_table` lists the new names.
- **New test file `tests/roadmap/test_roadmap_status_rows.py`.** The three behaviors of the issue (`source_failed`, `row_names`, `ledger_per_row`) need the real runners of the status rows over the web fake. Existing files keep their concerns and only change the expected row lists.

## Rejected alternatives

- **Keep one row and re-raise the first error after the three reads.** The row would still count one result for three sources, so a Cloudflare outage would suspend the project metrics. The probe on the unchanged code shows one `success` for all three reads.
- **Count a failed read in a new counter and keep the row green.** The alert `RoadmapServiceJobsFailing` already reads `devops_cli_service_jobs_total` by `row`. A second counter needs a second rule and hides the failure from the ledger that suspends a failing row.
- **Put the status rows before `implement`.** Evidence: `_execute_due_rows` runs the rows of a lane in order and one at a time, so a status page that times out first delays `implement` by the timeout.
