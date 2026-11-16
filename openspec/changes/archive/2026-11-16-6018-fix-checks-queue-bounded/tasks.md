# Tasks

## 1. Behavior: the unit record, one Job for each pull request, and the deadline outcome

- [x] 1.1 Write failing tests: in mode `on` the attempt after the TTL is 2 and an `error` gets no Job, mode `plan` writes no record, a second check of a head waits for the live Job, and a Job that its deadline ended is `deadline` with no next attempt
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_fix_checks_row.py`
- [x] 1.2 Add `fix_checks.units`, `FixDue.units`, the record write of `_report`, `_last_try`, the one live Job for each pull request, and `OUTCOME_DEADLINE`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_fix_checks_row.py`

## 2. Behavior: the wait limit of a waiting fix Job

- [x] 2.1 Write failing tests: a waiting fix Job holds a place only for a repository of `service.repos`, a Job past `roadmap.fix_checks.max_wait_minutes` is deleted with a log line, a Job within it stays, and the delete policy admits only the delete of a waiting fix Job
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_fix_checks_row.py tests/roadmap/implement/test_roadmap_implement_submit.py tests/roadmap/stage/test_roadmap_stage_submit.py`
- [x] 2.2 Add the setting, `waits`, `stale` and `model_slots(now=)`, the delete of `_expire`, and the CEL of `roadmap-service-job-deletes`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_fix_checks_row.py tests/roadmap/implement/test_roadmap_implement_submit.py tests/roadmap/stage/test_roadmap_stage_submit.py`

## 3. Behavior: the watch row and the ready path of the step

- [x] 3.1 Write failing tests: a missing CronJob or limits that do not nest give `round_error` and the row goes on, the row asks for `ready_only`, and the ready path skips a check that failed after the read of the row
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_watch_row.py tests/roadmap/steps/test_roadmap_step_fix_checks.py`
- [x] 3.2 Add `round_failed`, the guard of `watch_round`, and `ready_only`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_watch_row.py tests/roadmap/steps/test_roadmap_step_fix_checks.py`

## 4. Behavior: the panel and the alert

- [x] 4.1 Write failing tests: the panel draws Started, Repaired, No result line and Other, and the alert fires for `deadline`
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] 4.2 Change the panel targets, the alert expression and the counter series
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py tests/prometheus/test_k8s_monitoring_alerting.py`

## 5. Documents

- [x] 5.1 Update `docs/CLUSTER.md`, `docs/roadmap/job-success.md`, ADR 0021, the Role comment, and the generated setting tables
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
