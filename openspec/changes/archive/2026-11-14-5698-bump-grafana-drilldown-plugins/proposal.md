# Proposal: #5698

## Why
Grafana Advisor warns that newer releases exist for the preinstalled Drilldown application plugins. This change bumps all four plugins to release 3.2.0.

Closes #5698

## What Changes
Bump the pinned versions of `grafana-lokiexplore-app`, `grafana-metricsdrilldown-app`, `grafana-pyroscope-app`, and `grafana-exploretraces-app` to `3.2.0` in `k8s/monitoring/grafana-values.yaml`.

## Capabilities
### New Capabilities
None.

### Modified Capabilities
- `k8s/monitoring/grafana-values.yaml`: Pins all four Drilldown application plugins to release 3.2.0.

## Impact
At restart, Grafana installs release 3.2.0 of each Drilldown plugin.

## Feasibility
Upstream Grafana plugin releases confirm version 3.2.0 compatibility with Grafana 13.

## Existing Tool Considered
Grafana preinstall sync installed through Helm values is the standard mechanism.
