# Proposal

## Why

The alternatives check of #2950 ran 34 times over 14 days but searched about 4 times, and every verdict was not-applicable. No metric, alert or dashboard panel showed this, so the owner found it only in Firecrawl usage. The change makes the check's coverage and search activity visible.

## What Changes

- Declare the gauges `devops_cli_roadmap_alternatives_unchecked_items` and `devops_cli_roadmap_alternatives_oldest_check_age_seconds`, and the histogram `devops_cli_roadmap_alternatives_searches`, in `src/devops_cli/telemetry/instruments.py`.
- Record the three instruments from the alternatives job in `src/devops_cli/roadmap/alternatives.py` through the existing `emit()` path.
- Add the alert `RoadmapServiceAlternativesNotSearching` to `k8s/monitoring/prometheus-values.yaml` with a promtool unit test in `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`.
- Add a panel to the Roadmap dashboard `k8s/monitoring/dashboards/devops-cli.json` that reads the three instruments.
- Document the instruments in `docs/TELEMETRY.md` and the alert in `k8s/README.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `metric-instruments`: Alternatives coverage instruments
- `roadmap-alternatives`: Coverage gauges of a round, Searches per check
- `roadmap-service-alerts`: Alert on no alternatives search
- `telemetry-dashboard`: Alternatives coverage panel

## Impact

- Code: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/alternatives.py`, `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/dashboards/devops-cli.json`
- Documents: `docs/TELEMETRY.md`, `k8s/README.md`
- Tests: `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`

## Feasibility

- `read_file` on `src/devops_cli/telemetry/instruments.py` showed the `Instrument` dataclass, `InstrumentKind` with COUNTER, GAUGE and HISTOGRAM, the `INSTRUMENTS` list and `emit()`. The new instruments join that list and use `emit()`.
- `search_code` for `roadmap_alternatives_total` showed the counter in `docs/TELEMETRY.md:83`, the rule text in `k8s/README.md:615` and the archived change `openspec/changes/archive/2026-10-29-2652-alternatives-service-row/`. The alternatives job already emits a metric, so the new instruments use the same path.
- `file_symbols` on `src/devops_cli/roadmap/alternatives.py` showed `AlternativesTools.search_web`, `_spent`, `plan_alternatives`, `apply_alternatives` and `_check_one`. The round holds the search count and the written checks, so it can record the histogram at the write.
- `list_files` on `tests/fixtures/prometheus_rules` showed `roadmap_service_activity_tests.yaml`, the promtool unit test file of the activity group. The new alert gets its cases there.
- `list_files` on `k8s/monitoring/dashboards` showed `devops-cli.json`, the Roadmap dashboard, next to `project-metrics.json`. The new panel goes into `devops-cli.json`.
- First checks against the real system: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` for the declared instruments, `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` for the rule and its promtool test, and `uv run devops ci` for the whole gate.

## Existing Tool Considered

Prometheus and Grafana already cover the need. Prometheus collects the OTLP metrics and evaluates the alert rules, Grafana renders the dashboard panel, and promtool validates the rule and runs its unit test. The project already sends every metric through this path (`docs/TELEMETRY.md`, `k8s/monitoring/prometheus-values.yaml`). The change declares three instruments and one rule, and builds no metrics system.
