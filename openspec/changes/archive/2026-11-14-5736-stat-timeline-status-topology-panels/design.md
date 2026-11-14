# Design

## Decisions
- Stat panels layout:
  - Add "System Overview" row at y: 0.
  - Place 4 stat panels side by side (w: 6, h: 4 each, y: 1) for tunnel connections, ingress volume, AI gateway health, and brain decisions.
- Historical panels layout:
  - Add "Component State & Status History" row at y: 36.
  - Place a `state-timeline` panel at y: 37 (w: 12, h: 7, x: 0) querying `last_over_time(devops_cli_ai_gateway_healthy[5m])`.
  - Place a `status-history` panel at y: 37 (w: 12, h: 7, x: 12) querying `last_over_time(devops_cli_rag_drift_detected[5m])` and `last_over_time(devops_cli_upstream_service_status[5m])`.
- Value mappings:
  - Gateway health: 0 -> Unhealthy (red), 1 -> Healthy (green).
  - Status history: 0 -> Operational / Up to Date (green), 1 -> Drift / Minor (orange), 2 -> Major (orange), 3 -> Critical (red).

## Rejected alternatives
- Separate dashboards for state timeline and status history: Rejected because keeping them with system topology gives unified situational context.
