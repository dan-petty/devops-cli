# Proposal

## Why

Nothing measures how long an item waits in a roadmap state. Items sat in Ready, Planned and as stopped drafts for hours or days before a person saw them (#2919). The change adds age gauges, one alert and a panel so a stuck item is visible.

## What Changes

- Add the age-of-oldest-item gauges for new, ready, planned, in-progress, in-review and blocked, and the age-of-oldest-claim gauge, to INSTRUMENTS in src/devops_cli/telemetry/instruments.py
- Compute each age from the label event time with an injectable clock in the roadmap metrics row
- Add one Prometheus alert rule for a stuck item, with the item number in the message, and a promtool unit test
- Add a Grafana panel for the age gauges beside the inbox panel
- Document the new metrics in docs/TELEMETRY.md
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `metric-instruments`: Roadmap age gauges are declared instruments
- `roadmap-service-alerts`: One alert fires for a stuck item
- `project-metrics-dashboard`: The dashboard shows the roadmap item age

## Impact

- Code: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/run.py`, `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/dashboards/project-metrics.json`
- Documents: `docs/TELEMETRY.md`
- Tests: `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/test_roadmap_run.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`

## Feasibility

- search_code for ROADMAP_STAGE_TOTAL showed the existing roadmap instrument and its emit path in src/devops_cli/telemetry/instruments.py, so the new gauges follow a path that exists.
- search_code for promtool showed tests/prometheus/test_k8s_monitoring_alerting.py runs the pinned promtool on each rule, and tests/fixtures/prometheus_rules/ holds the unit tests, so the alert rule and its test have a home.
- list_files of k8s/monitoring/dashboards showed project-metrics.json and devops-cli.json, so the age panel goes in an existing dashboard.
- First checks against the real system: `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` and `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`.

## Existing Tool Considered

Prometheus and Grafana already cover metric exposition, alert rules and panels, and the project uses them. No open tool computes the age of the oldest GitHub issue in a label state, so the change builds the age computation in the existing telemetry path. The written cost is the tokens to build, keep and fix the label-event read, the delta and the emit, plus the elapsed time of that work.
