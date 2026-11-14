# Design: #5698

## Context
Grafana preinstalls Drilldown plugins specified in `plugins` within `k8s/monitoring/grafana-values.yaml`. Currently three plugins are at version 3.1.0 while traces is at 3.2.0.

## Decisions
- Update `grafana-lokiexplore-app`, `grafana-metricsdrilldown-app`, and `grafana-pyroscope-app` to version `3.2.0`.
- Verify in integration test that all four Drilldown plugins pin to version 3.2.0.
