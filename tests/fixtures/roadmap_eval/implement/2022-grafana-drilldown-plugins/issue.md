## Problem

Grafana keeps four app plugins on its volume at 2.x: `grafana-lokiexplore-app`, `grafana-metricsdrilldown-app`, `grafana-pyroscope-app` and `grafana-exploretraces-app`. Their 3.0.0 releases need Grafana 13.1.0 or later. The grafana-community chart sets `[plugins] preinstall_auto_update=false` (community chart PR 791 for issue 787), so after #1624 moves Grafana to 13.2.4 these plugins do not update. Grafana's upgrade guide for 13 tells users to update plugins for React 19.

## Proposed fix

Pin each of the four plugins at a 3.x release in the chart's `plugins` value in `k8s/monitoring/grafana-values.yaml`, so the version is in git and Grafana installs it at start.

## Acceptance criteria

- [ ] A test requires each of the four plugins with a pinned version in the Grafana values.
- Pending a person: after the sync, the Drilldown apps open and `GET /api/plugins` lists each plugin at the pinned version.
