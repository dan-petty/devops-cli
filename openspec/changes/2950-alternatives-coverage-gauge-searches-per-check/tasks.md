# Tasks

## 1. Declare the three alternatives instruments

Reads: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`, `docs/TELEMETRY.md`. Changes: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [ ] 1.1 Add a case to `tests/telemetry/test_telemetry_instruments.py` that asserts the three new names are in `INSTRUMENTS` with their kinds, and run `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` to see it fail, and verify that `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` fails on the base
- [ ] 1.2 Add `ALTERNATIVES_UNCHECKED_ITEMS` as a gauge, `ALTERNATIVES_OLDEST_CHECK_AGE` as a gauge in seconds, and `ALTERNATIVES_SEARCHES` as a histogram, each with its description, and add them to `INSTRUMENTS`, and verify that `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 2. Record the coverage gauges and the searches histogram

Reads: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/test_roadmap_alternatives.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_alternatives.py`.

- [ ] 2.1 Add cases to `tests/roadmap/test_roadmap_alternatives.py` for the unchecked-items gauge, the oldest-check-age gauge and one histogram observation for each written check, and run `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` to see them fail, and verify that `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` fails on the base
- [ ] 2.2 At the end of a round, count the open items with no check and the age of the oldest check, and emit both gauges with the `repo` attribute. For each written check, emit one observation of the searches histogram with the `verdict` attribute and the number of Firecrawl searches that the check ran, and verify that `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` passes

## 3. Add the alert rule and its promtool unit test

Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`.

- [ ] 3.1 Add `RoadmapServiceAlternativesNotSearching` to the `roadmap-service-activity` group with the expression `increase(devops_cli_firecrawl_searches_total{job="roadmap-service"}[3d]) == 0 and devops_cli_roadmap_alternatives_unchecked_items{job="roadmap-service"} > 0`, severity warning, and an annotation that names `{{ $labels.repo }}`. Add the firing, the search-in-window and the no-unchecked-items cases to the promtool unit test file, and verify that `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## 4. Add the alternatives panel to the Roadmap dashboard

Reads: `k8s/monitoring/dashboards/devops-cli.json`, `tests/prometheus/test_k8s_monitoring_dashboards.py`. Changes: `k8s/monitoring/dashboards/devops-cli.json`.

- [ ] 4.1 Add one panel to `k8s/monitoring/dashboards/devops-cli.json` with a query for each of the three instruments: the unchecked-items gauge and the oldest-check-age gauge with `last_over_time`, and the searches histogram with `histogram_count`, and verify that `uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py` passes

## 5. Document the instruments and the alert

Reads: `docs/TELEMETRY.md`, `k8s/README.md`. Changes: `docs/TELEMETRY.md`, `k8s/README.md`.

- [ ] 5.1 Add the three instruments to the table of `docs/TELEMETRY.md` with their types, units and descriptions. Add the alert and the panel to the roadmap service section of `k8s/README.md`, and verify that `uv run devops ci docs` passes
- [ ] 5.2 docs/TELEMETRY.md and k8s/README.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
