# Proposal: #7064

## Why

Unfiltered `devops roadmap eval grades --window 7d` fails against cluster Loki with HTTP 400 (`maximum number of series (500) reached for a single query`).
Every grade query currently carries all stream labels (including per-pod names of ephemeral `stage` and `fix-plan` Job pods) and unused extracted labels into `count_over_time(... [7d])` and value range aggregations, blowing past Loki's 500-series limit.
Testing live cluster Loki on 2026-11-25 confirmed that even with `| keep roadmap_job, repo, version, success, infra`, `COUNTS` over `[7d]` still exceeds 500 series due to version churn across repositories, while `[84h]` half-windows stay under 500 (`261` and `257` series). Closes #7064.

## What Changes

- Add a LogQL `keep` stage in `src/devops_cli/roadmap/job_grade_report.py` before `[window]` (and before `| unwrap` on efficiency queries) so each query retains only the labels its `sum by` / `by` aggregation and filters require (`COUNTS`, `CLASSES`, `DRAFTED`, `FIRST_PASSES`, and all efficiency queries).
- Add bounded recursive window halving (down to a `1h` floor) and series summation in `src/devops_cli/roadmap/job_grade_report.py` for count grade queries when Loki answers HTTP 400 containing `maximum number of series`, using `query_loki_metrics(..., at=...)` anchored at a single timestamp while leaving all other HTTP 400 errors fatal.
- Add `keep` stage evaluation support to `LokiFake` in `tests/support/fakes/loki.py`.
- Add unit and CLI regression tests in `tests/roadmap/test_job_grade_report.py` and document the behavior in `docs/roadmap/job-success.md`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-job-grades`: Restrict each grade query to only its used labels via LogQL `keep`, and split count grade queries in half (to a `1h` floor) when Loki rejects a window for `maximum number of series`.

## Impact

- Code: `src/devops_cli/roadmap/job_grade_report.py`
- Documents: `docs/roadmap/job-success.md`
- Tests: `tests/roadmap/test_job_grade_report.py`, `tests/support/fakes/loki.py`

## Feasibility

- Verified against live cluster `svc/loki` in namespace `logging` on 2026-11-25: `24h` counts and `tokens_sum` returned identical values with `| keep`; `[7d]` `CLASSES`, `DRAFTED`, `FIRST_PASSES`, `TOKENS_SUM`, and `TOKENS_P50` all succeeded with `| keep`; `[7d]` `COUNTS` returned HTTP 400 (`maximum number of series (500) reached`), and both `[84h]` halves (`261` and `257` series) succeeded.
- Verified Grafana Loki LogQL grammar requires `| keep` inside the log pipeline before `| unwrap`.

## Existing Tool Considered

Uses Grafana Loki's built-in LogQL `keep` label filter (sibling of `drop`, already used in `RESULT_LINES` and telemetry dashboards) combined with client-side binary halving over `query_loki_metrics(..., at=...)`, instead of raising cluster `max_query_series` limits; estimated cost is ~20k tokens and 0.5 hours, with no external library added or replaced.
