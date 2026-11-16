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

- [x] 3.1 Write failing tests: `roadmap.metrics.interval_minutes` defaults to 13, a variable sets it, the next round uses it, and the window of failed deliveries grows with it
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_row_cadence_settings.py tests/roadmap/test_roadmap_run_row_cadence.py tests/github/test_hook_deliveries.py`
- [x] 3.2 Add `RoadmapMetricsConfig`, give the `metrics` row its cadence, and pass the window from the setting
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_row_cadence_settings.py tests/roadmap/test_roadmap_run_row_cadence.py tests/github/test_hook_deliveries.py tests/security/test_config_declarations.py`

## 4. Source rule

- [x] 4.1 Add the ast-grep rule `github-request-scope-row` with its cases, and list it in the construct gate
  - Verification: `$ uv run devops ci --check --only constructs`

## 5. Documents

- [x] 5.1 Name the loops in `docs/CLUSTER.md` and `docs/TELEMETRY.md`, add `metrics` to the cadence rows, and regenerate the settings documents
  - Verification: `$ uv run devops docs check`

## Workflow follow-up

- #6013 caches the issue data that the rows read again; the measurement comment of the pull request names the reads to cache first.
- Pending a person: set `roadmap.metrics.interval_minutes` in the ConfigMap if the budget still holds rounds after the release.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
