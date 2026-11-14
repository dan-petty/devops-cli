# Proposal: #5736

## Why
Operators need high-level overview metrics and operational state history in the System Topology dashboard. This change adds summary stat panels and historical state timeline and status history panels to the dashboard. Closes #5736.

## What Changes
- Expand `k8s/monitoring/dashboards/system-topology.json` (`System Topology & Service Map`).
- Add a top "System Overview" row with 4 `stat` panels:
  1. Active Cloudflare tunnel connections.
  2. 1-hour ingress request volume.
  3. AI gateway health probe status.
  4. 1-hour autonomous brain decisions count.
- Add a bottom "Component State & Status History" row with 2 panels:
  1. A `state-timeline` panel tracking AI gateway operational availability over time.
  2. A `status-history` panel tracking RAG knowledge drift detection and upstream cloud services status.
- Update tests in `tests/prometheus/test_k8s_monitoring_dashboards.py`.
- Update the system topology dashboard specification in OpenSpec.

## Capabilities
- `system-topology-dashboard`: Provide overview stat panels, state timeline, and status history panels in the system topology dashboard.

## Impact
Improves operational awareness by showing key summary metrics and historical state transitions without extra cluster load.

## Feasibility
Prometheus metrics for Cloudflare tunnel connections, Traefik requests, AI gateway health, RAG drift, and upstream status are already active and validated.

## Existing Tool Considered
Grafana native Stat, State Timeline, and Status History panel visualizations. Using these built-in panel types requires no custom plugins.
