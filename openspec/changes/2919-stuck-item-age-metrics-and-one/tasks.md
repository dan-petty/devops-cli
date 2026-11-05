# Tasks

## 1. Declare the roadmap age gauges

Reads: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 1.1 In `tests/telemetry/test_telemetry_instruments.py`, add a test that `INSTRUMENTS` holds `devops_cli_roadmap_item_age_seconds`, `devops_cli_roadmap_oldest_item_number` and `devops_cli_roadmap_claim_age_seconds` as gauges, that the first and the last have the unit `s`, that `ROADMAP_AGE_LABELS` is `("repo", "state", "plan")`, and that the description of each item gauge names those labels. The test fails on the base.
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py`
- [x] 1.2 In `src/devops_cli/telemetry/instruments.py`, add `ROADMAP_ITEM_AGE`, `ROADMAP_OLDEST_ITEM` and `ROADMAP_CLAIM_AGE` as gauges after `ROADMAP_STAGE_TOTAL`, add `ROADMAP_AGE_LABELS`, and add the four names to `INSTRUMENTS` and `__all__`. The test passes after the change.
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py`

## 2. Read the label changes of one issue

Reads: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `tests/roadmap/test_roadmap_github_store.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap_github_fake.py`. Changes: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `tests/roadmap/test_roadmap_github_store.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap_github_fake.py`.

- [x] 2.1 Add the tests of `label_changes`. In `tests/roadmap/test_roadmap_github_store.py`, a recorded reply for `/repos/example/roadmap/issues/950/events?per_page=100` with a `labeled` event, a `commented` event and an `unlabeled` event, none with an `issue` key, gives two changes, oldest first, with `number` 950 and the actor, label and time of each. A listing with a `Link` next page reads the second page, and a failed page raises `GitHubOperationError`. In `tests/roadmap/test_roadmap_store_contract.py`, `InMemoryRoadmapStore.label_changes` returns the `labeled` and `unlabeled` changes of one issue only, oldest first, after `set_field` calls that a stepping clock times. In `tests/roadmap_github_fake.py`, make `GitHubFake` answer `issues/<number>/events` with the seeded events of that issue. The tests fail on the base.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_github_store.py tests/roadmap/test_roadmap_store_contract.py`
- [x] 2.2 In `src/devops_cli/roadmap/store.py`, add `label_changes(number)` to `RoadmapStore`. In `src/devops_cli/roadmap/github_store.py`, add `issue_events_endpoint(repo, number)`, a payload class for an event with no `issue` key, and `GitHubRoadmapStore.label_changes`, which reads the listing through `_listing` and keeps the `labeled` and `unlabeled` events. In `src/devops_cli/roadmap/memory_store.py`, return the recorded changes of the issue that are labeled or unlabeled. The tests pass after the change.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_github_store.py tests/roadmap/test_roadmap_store_contract.py`

## 3. Send the age gauges from the metrics report

Reads: `src/devops_cli/github/metrics.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/telemetry/instruments.py`, `tests/github/test_github_metrics.py`, `tests/conftest.py`. Changes: `src/devops_cli/github/metrics.py`, `tests/github/test_github_metrics.py`, `tests/conftest.py`.

- [x] 3.1 In `tests/github/test_github_metrics.py`, add tests over the in-memory store with a stepping clock and the `otlp` fixture, one for each scenario of the spec: an event at T and a clock at T plus 3600 sends 3600 and the item number; the oldest of two items; a label removed and added again; the `plan` flag from `stage.pr`; an empty pair sends 0 and 0 for both flags; the oldest claim; two rounds with no change read no events and a changed Status reads one issue; a store whose `label_changes` raises `GitHubOperationError` leaves the item counts sent, sends no age and logs a warning. Add a test over `GitHubFake` that `devops gh metrics --emit-telemetry` sends no age and no request that ends in `/events`. The tests fail on the base.
  - Verification: `uv run devops ci test tests/github/test_github_metrics.py`
- [x] 3.2 In `src/devops_cli/github/metrics.py`, add `ItemAgeMetric`, the field `item_ages` of `ProjectMetricsReport`, `get_item_age_metrics(store, repo, clock)` with the per-process cache and `reset_item_age_cache`, the parameters `item_ages: bool = False` and `clock` of `collect_project_metrics_report` with the typed catch, and the send of the three gauges in `emit_project_metrics_telemetry`. Add `reset_item_age_cache` to the entry `devops_cli.github.metrics` of the reset map in `tests/conftest.py`. The tests pass after the change.
  - Verification: `uv run devops ci test tests/github/test_github_metrics.py tests/invariants/test_architectural_invariants.py`

## 4. Ask for the ages in the metrics row of the Service

Reads: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_run.py`. Changes: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_run.py`.

- [x] 4.1 In `tests/roadmap/test_roadmap_run.py`, add a test that `_run_metrics_adapter` over `InMemoryRoadmapStore` with a Blocked item sends `devops_cli_roadmap_item_age_seconds` for `state` `blocked` with the labels `repo`, `state` and `plan`, and logs no warning. The test fails on the base.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_run.py`
- [x] 4.2 In `_run_metrics_adapter` of `src/devops_cli/roadmap/run.py`, pass `item_ages=True` to `collect_project_metrics_report`. The test passes after the change.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_run.py`

## 5. Add the stuck-item alert and its promtool unit test

Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, `k8s/README.md`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `k8s/README.md`, `tests/fixtures/prometheus_rules/roadmap_service_items_tests.yaml` (new).

- [x] 5.1 Create `tests/fixtures/prometheus_rules/roadmap_service_items_tests.yaml` with the five cases of the spec (Blocked over a day with item 2919 in the summary, Ready with a plan over a day, Ready with no plan, Blocked under a day, a series of the job `devops-cli`). In `tests/prometheus/test_k8s_monitoring_alerting.py`, add the group `roadmap-service-items` and the fixture to `ROADMAP_SERVICE_GROUP_TESTS`, the two age series and the number series to `SERVED_SERIES`, and `("RoadmapServiceItemStuck", "warning")` to `test_the_baseline_rule_set`. The tests fail on the base.
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] 5.2 In `k8s/monitoring/prometheus-values.yaml`, add the group `roadmap-service-items` after the group `roadmap-service-activity`, with `RoadmapServiceItemStuck`: `for: 0m`, severity `warning`, the literal 86400, a comment that names the reason for the literal, and a description that ends with `(k8s/README.md, Roadmap service)`. In `k8s/README.md`, add a paragraph and a table row for the alert to the section "Roadmap service", after the table of the activity group, with the command that clears it: `devops roadmap inbox`. The tests pass with promtool 3.15.1 on PATH.
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## 6. Add the age panel to the project dashboard

Reads: `k8s/monitoring/dashboards/project-metrics.json`, `tests/telemetry/test_telemetry_instruments.py`, `tests/prometheus/test_k8s_monitoring_dashboards.py`. Changes: `k8s/monitoring/dashboards/project-metrics.json`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 6.1 In `tests/telemetry/test_telemetry_instruments.py`, add a test that `project-metrics.json` holds the panel "Oldest Item Age by State" with the two queries of the spec and the unit `s`, that its grid position is `x` 0, `y` 34, `w` 12 and `h` 8, and that no panel overlaps another. The test fails on the base.
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py`
- [x] 6.2 In `k8s/monitoring/dashboards/project-metrics.json`, add the panel with a new id and a description that says it shows the latest value of each series in the time range, and add 8 to `gridPos.y` of every panel at or below `y` 34. The tests pass after the change.
  - Verification: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py tests/prometheus/test_k8s_monitoring_dashboards.py`

## 7. Regenerate the documents

Reads: `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`. Changes: `docs/TELEMETRY.md`.

- [ ] 7.1 Run `uv run devops docs generate --sync-readme`. Only `docs/TELEMETRY.md` changes: it gains three rows from the descriptions of the instruments.
  - Verification: `uv run devops docs check`

## Criteria

- The gauges are declared instruments and are sent through `emit`.: group 3
- The alert rule has a promtool unit test.: group 5
- A test shows the age is computed from the label event time or the record, with a fake clock.: group 3
- `uv run devops ci` passes.: group 7

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
