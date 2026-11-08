# Proposal

## Why

The row `metrics` of the status lane reads the project metrics, the GitHub status page and the Cloudflare status page (#4052). Each read sits in its own `except Exception` that only logs a warning. A failed read still counts `success` for the row and stamps `schedule.json`. So the job counter, the record of failed rounds and the alert `RoadmapServiceJobsFailing` never see a failed collection. The status readers already raise `ServiceStatusError`, and the row hides it.

## What Changes

- Split `_run_metrics_adapter` in `src/devops_cli/roadmap/run.py` into three runners. `metrics` keeps the project metrics and the clone. `github_status` and `cloudflare_status` are new rows that need no clone.
- Remove the three `except Exception` blocks. A failed read raises, and the row of that source fails alone.
- Add the two rows to the end of `STATUS_LANE_ROWS`, so the order is `metrics`, `implement`, `stage_ready`, `release_comments`, `github_status`, `cloudflare_status`. A slow status page then never delays `implement`. Both rows use `DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES`; no interval changes.
- Update `build_stub_table` and the docstrings of `run.py` that name the rows.
- Update item 17 of `k8s/README.md` (the rows of the status lane and what each reads), `CONTEXT.md` (the status lane sentence) and the spec `roadmap-implement-job` where they list the rows. Item 12 lists only the rows that send GitHub requests, so it stays as it is.
- Rollout: no setting is removed, renamed or tightened. The example and the live ConfigMap name no row, so neither changes. A `schedule.json` and a `service-failures.json` written before this change hold no entry for the two new rows. The first round makes both rows due once (`first_run_due`), and the entry of `metrics` stays valid. The test of #4093 that loads the example ConfigMap into `Settings` must still pass.
- The change carries a spec delta, because the rows, the counter labels and the failure of a row are observable: `roadmap-implement-job` (MODIFIED) and `roadmap-service-counters` (ADDED).
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The rows of each lane
- `roadmap-service-counters`: A status read fails its own row

## Impact

- Code: `src/devops_cli/roadmap/run.py`
- Documents: `k8s/README.md`, `CONTEXT.md`
- Tests: `tests/roadmap/test_roadmap_status_rows.py` (new), `tests/roadmap/test_roadmap_run_metrics.py`, `tests/roadmap/test_roadmap_run_failure_ledger.py`, `tests/roadmap/test_roadmap_run_lanes.py`, `tests/roadmap/test_roadmap_run_due_table.py`, `tests/roadmap/test_roadmap_run_job_rows.py`, `tests/roadmap/test_roadmap_run_service.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/stage/test_roadmap_stage_ready.py`, `tests/support/roadmap_run.py`

## Feasibility

- Read at origin/main: `src/devops_cli/roadmap/run.py` lines 689 to 732 show `_run_metrics_adapter` with three `except Exception` blocks that call `logger.warning` and go on, then `return JobOutcome()`. `_execute_due_rows` counts `success`, calls `_record_success` and `failures.succeeded` for any runner that returns, so the swallowed error is the cause.
- Read `src/devops_cli/telemetry/service_status.py`: `fetch_statuspage_summary` raises `ServiceStatusError` on an `httpx2.HTTPError` and on a parse error, and `fetch_github_status` and `fetch_cloudflare_status` call it. `emit_service_status_telemetry` only emits. So a row can call them with no wrapper.
- The probe `uv run devops ci test tests/roadmap/test_roadmap_run_metrics.py tests/roadmap/test_roadmap_status_rows.py` on the unchanged code shows the cause: the log holds `GitHub service status collection failed` and `Cloudflare service status collection failed`, and the call returns.
- Read `src/devops_cli/server/counter_series.py`: `prime_counter` reads `STATUS_LANE_ROWS`, so the new rows get their label series at zero with no edit.
- Read the alert `RoadmapServiceJobsFailing` in `k8s/monitoring/prometheus-values.yaml`: it groups on `repo`, `lane` and `row`, so a new row alerts alone with no rule edit. `grep -rn 'row="metrics"' k8s/monitoring` finds nothing, so no alert or dashboard selects the old row for a status read.
- Read `build_stub_table`: its `kept.get(name, True)` keeps a row that the map does not name, so the new rows stay in a stub table by default.
- Read item 12 of `k8s/README.md`: the label `row` of `devops_cli_github_requests_total` lists rows that send GitHub requests. The two new rows send none, so they do not join that list.
- Not run: the Service itself. The change reads and edits code and tests only.

## Existing Tool Considered

The row table `JobRow`, the ledger `FailureLedger` and the readers of `telemetry/service_status.py` already hold the need: a row that raises is counted, stamped and suspended by the code that exists. No library is needed. The change builds no new code path; it deletes the three `except Exception` blocks of `_run_metrics_adapter`, and moves each read to a runner of its own. Cost: about 45k tokens and 2.5 hours to build, about 2k tokens a quarter to keep, and about 10k tokens and 0.5 hours to fix.

## Dependencies

#4048 (the gauge and alert for a state record that was not kept) is merged. Both changes edit `run.py` and `k8s/README.md`.
