# Tasks

## 1. Declare the three alternatives instruments

Reads: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 1.1 Add a test to `tests/telemetry/test_telemetry_instruments.py` that finds `devops_cli_roadmap_alternatives_unchecked_items` and `devops_cli_roadmap_alternatives_oldest_check_age_seconds` as gauges with the units `1` and `s`, and `devops_cli_roadmap_alternatives_searches` as a histogram with the unit `1`, in `INSTRUMENTS`, and verify that `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` fails on the base
- [x] 1.2 Add `ROADMAP_ALTERNATIVES_UNCHECKED_ITEMS`, `ROADMAP_ALTERNATIVES_OLDEST_CHECK_AGE` and `ROADMAP_ALTERNATIVES_SEARCHES` to `src/devops_cli/telemetry/instruments.py`, each with a description in the style of `ROADMAP_ALTERNATIVES_TOTAL`, and add them to `INSTRUMENTS` and `__all__`, and verify that `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 2. Measure the coverage of a round

Reads: `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_alternatives.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_alternatives.py`.

- [x] 2.1 Add tests to `tests/roadmap/test_roadmap_alternatives.py` for `Coverage`: 10 eligible items with 4 checks and one failed check in the retry delay give 6 unchecked; an In Progress item and an item of an untrusted author are not counted; a check written 72 hours before `now` gives the age 259200 s; no check gives no age; `--item` gives no coverage. Add a test with the `otlp` fixture that `record_coverage` sends the two gauges with `repo` and sends nothing for a plan with no coverage or with `off_reason`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` fails on the base
- [x] 2.2 In `src/devops_cli/roadmap/alternatives.py`, add the frozen dataclass `Coverage` (the count of unchecked items and the age of the oldest check as a `timedelta` or `None`). Make `select_items` read the check time of each eligible item before it tests the retry delay, and return the coverage in a new field `Selection.coverage` (`None` for `item_number`). Add `AlternativesPlan.coverage`, set it in both returns of `plan_alternatives` that follow the selection, and add `record_coverage(plan)`, which emits `ROADMAP_ALTERNATIVES_UNCHECKED_ITEMS` and, when there is an age, `ROADMAP_ALTERNATIVES_OLDEST_CHECK_AGE` with `{"repo": plan.repo}`. Add `Coverage` and `record_coverage` to `__all__`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` passes

## 3. Record the coverage in the Service row

Reads: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_alternatives.py`. Changes: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_alternatives.py`.

- [x] 3.1 Add tests to `tests/roadmap/test_roadmap_alternatives.py` that the row (`_alternatives_row().runner`) sends both gauges for a round that checks items, and for a round with every check current (the unchecked gauge is 0 and the model gets no request); that a repository where the check is off sends none; and that `devops roadmap alternatives` with no flag, with `--confirm` and with `--item` sends none. Verify that `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` fails on the base
- [x] 3.2 In `_run_alternatives_adapter` of `src/devops_cli/roadmap/run.py`, call `record_coverage(plan)` right after `plan_alternatives` and before `apply_alternatives`. Add `record_coverage` to the one module-level import from `devops_cli.roadmap.alternatives`, because `tests/roadmap/test_roadmap_run.py` requires that import to stay module level. Verify that `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` passes

## 4. Observe the searches of each written check

Reads: `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_alternatives.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_alternatives.py`.

- [x] 4.1 Add tests to `tests/roadmap/test_roadmap_alternatives.py` with the `otlp` fixture: a check with the verdict `none` after 3 searches gives the point `{verdict="none"}` with the value 3; a `docs(...)` item gives `{verdict="not-applicable"}` with 0; a failed check, a check skipped because the body changed, and a plan that is not applied give no point. Verify that `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` fails on the base
- [x] 4.2 In `apply_alternatives` of `src/devops_cli/roadmap/alternatives.py`, emit `ROADMAP_ALTERNATIVES_SEARCHES` with `len(check.queries)` and `{"verdict": check.verdict.value}` next to `emit(ROADMAP_ALTERNATIVES_TOTAL, ...)`, and update the docstring of the function. Verify that `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` passes

## 5. Add the alert, its promtool cases and the pins

Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, `k8s/README.md`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, `k8s/README.md`.

- [x] 5.1 Add the six promtool cases of the spec to `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, with the real label sets (`job="roadmap-service"`, `instance="roadmap-service"`, `result="ok"` and `result="402"` on the counter, `repo="example/app"` on the gauge). Add the fourth entry of `ROADMAP_SERVICE_ACTIVITY_RULES` (the count of searches through `_window_count(..., "3d")`), `RoadmapServiceAlternativesNotSearching` to `test_the_baseline_rule_set`, and `ROADMAP_ALTERNATIVES_UNCHECKED_ITEMS.name` to `SERVED_SERIES`. Verify that `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [x] 5.2 Add the alert `RoadmapServiceAlternativesNotSearching` to the group `roadmap-service-activity` of `k8s/monitoring/prometheus-values.yaml`: `for: 1h`, severity `warning`, the expression of design.md, a summary and a description that name `{{ $labels.repo }}` and end with `(k8s/README.md, Roadmap service)`. Add its row to the table "Alerts" of the section "Roadmap service" in `k8s/README.md`, with the steps to do when it fires. Verify that `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes with promtool 3.15.1 on the PATH (`uv run devops install-tools --tool promtool`)

## 6. Add the Alternatives Check row to the devops-cli dashboard

Reads: `k8s/monitoring/dashboards/devops-cli.json`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `k8s/monitoring/dashboards/devops-cli.json`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 6.1 Add a test to `tests/telemetry/test_telemetry_instruments.py`, beside the test of "Embedding Cache Hit Share", that pins the row "Alternatives Check" and the queries of its three panels as the spec gives them, and verify that `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` fails on the base
- [x] 6.2 Add the row (id 49, `gridPos.y` 136) and the panels "Alternatives Unchecked Items", "Alternatives Oldest Check Age" (unit `s`) and "Alternatives Searches per Check" (ids 50 to 52, `w` 8, `y` 137) to `k8s/monitoring/dashboards/devops-cli.json`, each with a description and the datasource of the other panels (the description of the histogram panel states the limits of `increase()`, as `test_every_panel_counting_with_increase_states_its_limits` requires), and verify that `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 7. Document the instruments, the row and the alert

Reads: `docs/TELEMETRY.md`, `k8s/README.md`. Changes: `docs/TELEMETRY.md`, `k8s/README.md`.

- [x] 7.1 In step 14 of the section "Roadmap service" of `k8s/README.md`, say that each round sends the two gauges and each written check observes the histogram, and that the dashboard `devops-cli Telemetry` shows them in the row "Alternatives Check". In the section "Alerts", say that `RoadmapServiceAlternativesNotSearching` counts the searches of every job of the Service, refine too. Run `uv run devops docs generate --sync-readme` to write the three instruments to `docs/TELEMETRY.md`, and verify that `uv run devops ci docs` passes
- [x] 7.2 Run the whole gate and verify that `uv run devops ci` passes

## Criteria

- The instruments are declared and covered by the invariant that every metric is a declared instrument.: group 1
- The alert rule has a promtool unit test.: group 5
- `uv run devops ci` passes.: group 7

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
