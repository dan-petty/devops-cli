# Tasks

## 1. Behavior: each request of a Service round names its row

- [x] 1.1 Write failing tests: a worker round names `poll` or `webhook`, a scoped update names `webhook`, and no request of a round over every lane counts as `other`
  - Verification: `$ uv run devops ci test tests/github/test_service_limits.py tests/roadmap/test_roadmap_run_request_rows.py`
- [x] 1.2 Name the loop in the scopes of `RepoWorker`, and name `idle_check` for the read of the open work
  - Verification: `$ uv run devops ci test tests/github/test_service_limits.py tests/roadmap/test_roadmap_run_request_rows.py`

## 2. Behavior: one lane reads the open work

- [x] 2.1 Write a failing test: one poll of every lane reads the open issues once
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_request_rows.py`
- [x] 2.2 Give `idle` only to the lane of `intake` in `service_jobs`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_request_rows.py tests/roadmap/test_roadmap_run_lanes.py`

## 3. Behavior: the interval of the metrics row is a setting

- [x] 3.1 Write failing tests: `roadmap.metrics.interval_minutes` defaults to 13, a variable sets it, the next round uses it, and the section holds no backlog setting
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_row_cadence_settings.py tests/roadmap/test_roadmap_run_row_cadence.py`
- [x] 3.2 Add `RowIntervalConfig` and `RoadmapMetricsConfig`, and give the `metrics` row its cadence
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_row_cadence_settings.py tests/roadmap/test_roadmap_run_row_cadence.py tests/security/test_config_declarations.py tests/roadmap/test_roadmap_status_rows.py`

## 4. Behavior: no failed delivery is lost between two reads

- [x] 4.1 Write failing tests: a read 30 minutes after the last one counts the failed deliveries since it over two pages, a failed read keeps the start, and a gap of hours stops at the page limit with a warning
  - Verification: `$ uv run devops ci test tests/github/test_hook_deliveries.py`
- [x] 4.2 Keep the time of the last good read, list `status=failure` and follow the `Link` through `gh api --include`
  - Verification: `$ uv run devops ci test tests/github/test_hook_deliveries.py tests/roadmap/test_roadmap_run_metrics.py tests/prometheus/test_k8s_monitoring_alerting.py`

## 5. Source rule

- [x] 5.1 Add the ast-grep rule `github-request-scope-row` with its cases, and list it in the construct gate
  - Verification: `$ uv run devops ci --check --only constructs`

## 6. Documents

- [x] 6.1 Name the loops in `docs/CLUSTER.md` and `docs/TELEMETRY.md`, add `metrics` to the cadence rows, correct the window of failed deliveries in `docs/CLUSTER.md` and the alert text, and regenerate the settings documents
  - Verification: `$ uv run devops docs check`

## Workflow follow-up

- #6013 caches the issue data that the rows read again; the measurement comment of the pull request names the reads to cache first.
- Pending a person: set `roadmap.metrics.interval_minutes` in the ConfigMap if the budget still holds rounds after the release.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
