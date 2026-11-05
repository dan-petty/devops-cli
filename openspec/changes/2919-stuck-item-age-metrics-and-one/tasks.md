# Tasks

## 1. Declare the roadmap age gauges

Reads: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 1.1 In `tests/telemetry/test_telemetry_instruments.py`, add a test for the three gauges. `INSTRUMENTS` must hold `devops_cli_roadmap_item_age_seconds`, `devops_cli_roadmap_oldest_item_number` and `devops_cli_roadmap_claim_age_seconds` as gauges. The first and the last have the unit `s`. `ROADMAP_AGE_LABELS` is `("repo", "state", "plan")`. The description of each item gauge names those labels. The test fails on the base.
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py`
- [x] 1.2 In `src/devops_cli/telemetry/instruments.py`, add `ROADMAP_ITEM_AGE`, `ROADMAP_OLDEST_ITEM` and `ROADMAP_CLAIM_AGE` as gauges after `ROADMAP_STAGE_TOTAL`. Add `ROADMAP_AGE_LABELS`. Add the four names to `INSTRUMENTS` and `__all__`. The test passes after the change.
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py`

## 2. Read the label changes of one issue

Reads: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `tests/roadmap/test_roadmap_github_store.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap_github_fake.py`. Changes: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `tests/roadmap/test_roadmap_github_store.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap_github_fake.py`.

- [x] 2.1 Add the tests of `label_changes`. The tests fail on the base.
  - In `tests/roadmap/test_roadmap_github_store.py`, use a recorded reply for `/repos/example/roadmap/issues/950/events?per_page=100`. The reply holds a `labeled` event, a `commented` event and an `unlabeled` event. None has an `issue` key. The read gives two changes, oldest first. Each has `number` 950, and its actor, label and time.
  - A listing with a `Link` next page makes the read fetch the second page. A failed page raises `GitHubOperationError`.
  - In `tests/roadmap/test_roadmap_store_contract.py`, `InMemoryRoadmapStore.label_changes` returns the `labeled` and `unlabeled` changes of one issue only, oldest first. The test calls `set_field` with a stepping clock.
  - In `tests/roadmap_github_fake.py`, make `GitHubFake` answer `issues/<number>/events` with the seeded events of that issue.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_github_store.py tests/roadmap/test_roadmap_store_contract.py`
- [x] 2.2 Add the label changes to the stores. The tests pass after the change.
  - In `src/devops_cli/roadmap/store.py`, add `label_changes(number)` to `RoadmapStore`. In `src/devops_cli/roadmap/github_store.py`, add `issue_events_endpoint(repo, number)`. Add a payload class for an event with no `issue` key.
  - Add `GitHubRoadmapStore.label_changes`. It reads the listing through `_listing` and keeps the `labeled` and `unlabeled` events.
  - In `src/devops_cli/roadmap/memory_store.py`, return the recorded changes of the issue that are labeled or unlabeled.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_github_store.py tests/roadmap/test_roadmap_store_contract.py`

## 3. Send the age gauges from the metrics report

Reads: `src/devops_cli/github/metrics.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/telemetry/instruments.py`, `tests/github/test_github_metrics.py`, `tests/conftest.py`. Changes: `src/devops_cli/github/metrics.py`, `tests/github/test_github_metrics.py`, `tests/conftest.py`.

- [x] 3.1 In `tests/github/test_github_metrics.py`, add tests over the in-memory store. Use a stepping clock and the `otlp` fixture. Add one test for each scenario of the spec. The tests fail on the base.
  - An event at T and a clock at T plus 3600 sends 3600 and the item number. Other tests cover the oldest of two items, a label removed and added again, and the `plan` flag from `stage.pr`. An empty pair sends 0 and 0 for both flags. The oldest claim has its own test.
  - Two rounds with no change read no events. A changed Status reads one issue. A store whose `label_changes` raises `GitHubOperationError` leaves the item counts sent. It sends no age and logs a warning.
  - Add a test over `GitHubFake` that `devops gh metrics --emit-telemetry` sends no age and no request that ends in `/events`. Add a test that a round of one repository keeps the label times of another.
  - Verification: `uv run devops ci test tests/github/test_github_metrics.py`
- [x] 3.2 In `src/devops_cli/github/metrics.py`, add `ItemAgeMetric` and the field `item_ages` of `ProjectMetricsReport`. Add `get_item_age_metrics(store, repo, clock)` with the per-process cache and `reset_item_age_cache`. Add the parameters `item_ages: bool = False` and `clock` to `collect_project_metrics_report`, with the typed catch. Add the send of the three gauges in `emit_project_metrics_telemetry`. Add `reset_item_age_cache` to the entry `devops_cli.github.metrics` of the reset map in `tests/conftest.py`. The tests pass after the change.
  - Verification: `uv run devops ci test tests/github/test_github_metrics.py tests/invariants/test_architectural_invariants.py`

## 4. Ask for the ages in the metrics row of the Service

Reads: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_run.py`. Changes: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_run.py`.

- [x] 4.1 In `tests/roadmap/test_roadmap_run.py`, add a test. It runs `_run_metrics_adapter` over `InMemoryRoadmapStore` with a Blocked item. It sends `devops_cli_roadmap_item_age_seconds` for `state` `blocked`, with the labels `repo`, `state` and `plan`. It logs no warning. The test fails on the base.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_run.py`
- [x] 4.2 In `_run_metrics_adapter` of `src/devops_cli/roadmap/run.py`, pass `item_ages=True` to `collect_project_metrics_report`. The test passes after the change.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_run.py`

## 5. Add the stuck-item alert and its promtool unit test

Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, `k8s/README.md`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `k8s/README.md`, `tests/fixtures/prometheus_rules/roadmap_service_items_tests.yaml` (new).

- [x] 5.1 Create `tests/fixtures/prometheus_rules/roadmap_service_items_tests.yaml`. Give it the five cases of the spec and one case for a missing number series. The tests fail on the base.
  - The cases cover a blocked item over a day and a ready item with a plan. The blocked case names item 2919 in its summary. They also cover a ready item with no plan, a blocked item under a day and another job.
  - In `tests/prometheus/test_k8s_monitoring_alerting.py`, add the group `roadmap-service-items` and the fixture to `ROADMAP_SERVICE_GROUP_TESTS`. Add the two age series and the number series to `SERVED_SERIES`. Add `("RoadmapServiceItemStuck", "warning")` to `test_the_baseline_rule_set`.
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] 5.2 In `k8s/monitoring/prometheus-values.yaml`, add the group `roadmap-service-items` after the group `roadmap-service-activity`. The tests pass with promtool 3.15.1 on PATH.
  - Add `RoadmapServiceItemStuck` to it, with `for: 0m` and severity `warning`. Use the literal 86400. Add a comment that names the reason for the literal. The description ends with `(k8s/README.md, Roadmap service)`.
  - In `k8s/README.md`, add a paragraph and a table row for the alert to the section "Roadmap service". Put them after the table of the activity group. The row names the command that clears it: `devops roadmap inbox`.
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## 6. Add the age panel to the project dashboard

Reads: `k8s/monitoring/dashboards/project-metrics.json`, `tests/telemetry/test_telemetry_instruments.py`, `tests/prometheus/test_k8s_monitoring_dashboards.py`. Changes: `k8s/monitoring/dashboards/project-metrics.json`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 6.1 In `tests/telemetry/test_telemetry_instruments.py`, add a test for the dashboard. The test checks that `project-metrics.json` holds the panel "Oldest Item Age by State". The panel has the two queries of the spec and the unit `s`. Its grid position is `x` 0, `y` 34, `w` 12 and `h` 8. No panel overlaps another. The test fails on the base.
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py`
- [x] 6.2 In `k8s/monitoring/dashboards/project-metrics.json`, add the panel with a new id. Its description says it shows the latest value of each series in the time range. Add 8 to `gridPos.y` of every panel at or below `y` 34. The tests pass after the change.
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py tests/prometheus/test_k8s_monitoring_dashboards.py`

## 7. Regenerate the documents

Reads: `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`. Changes: `docs/TELEMETRY.md`.

- [x] 7.1 Run `uv run devops docs generate --sync-readme`. Only `docs/TELEMETRY.md` changes. It gains three rows from the descriptions of the instruments.
  - Verification: `uv run devops docs check`

## Criteria

- The gauges are declared instruments and are sent through `emit`.: group 3
- The alert rule has a promtool unit test.: group 5
- A test shows the age is computed from the label event time or the record, with a fake clock.: group 3
- `uv run devops ci` passes.: group 7

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
