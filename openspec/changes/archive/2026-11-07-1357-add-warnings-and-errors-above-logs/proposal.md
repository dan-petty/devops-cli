# Proposal

## Why

Issue #1357: On 2026-10-08 the owner asked for *SRE / Service Performance & Logs* (`k8s/monitoring/dashboards/sre-service.json`, uid `devops-sre-service`) to show two log panels: warnings and higher on top, and every line below it.

Today, Row 11 (*Service Logs & Live Stream*) holds a single logs panel (id 12, *Live Service Logs (Loki)*) querying `{namespace=~"$namespace", pod=~"$pod"}`. The Loki datasource returns at most 1,000 lines per query, which in a typical namespace covers only the newest ~15 minutes of logs. Warning and error lines older than 15 minutes are never fetched, and those that are fetched are buried among informational logs. Furthermore, pod streams carry `pod` as structured metadata rather than an indexed label; matching `pod` inside the stream selector blanks the panel whenever a specific pod is selected.

## What Changes

- `k8s/monitoring/dashboards/sre-service.json`:
  - Add a new logs panel in Row 11 titled *Warnings & Errors (Loki)* (id 21) at `h: 8, w: 24, x: 0, y: 39` with query `{namespace=~"$namespace"} | pod=~"$pod" | detected_level=~"(?i)(warn|warning|error|err|critical|fatal|panic)"` and a description mentioning namespace, pods, and Kubernetes Warning events.
  - Move panel 12 (*Live Service Logs (Loki)*) to `y: 47` with `h: 12`, update its query to `{namespace=~"$namespace"} | pod=~"$pod"` (moving `pod` to a LogQL label filter stage to fix the pod selection blanking defect), and remove mention of "service" from its description.
  - Shift Row 18 (*Continuous Profiling & Flamegraphs (Pyroscope)*) to `y: 59`, and flamegraphs 19 and 20 to `y: 60` and `y: 72`.
- `k8s/logging/loki-values.yaml`:
  - Set `discover_log_levels: true` under `loki.limits_config` with a comment naming the *Warnings & Errors (Loki)* panel that depends on it.
- `k8s/README.md`:
  - Update the dashboard row to its real title *SRE / Service Performance & Logs* and list both log panels (*Warnings & Errors (Loki)* and *Live Service Logs (Loki)*).
- Tests:
  - Add a test in `tests/commands/k8s/test_k8s.py` verifying `discover_log_levels: true` in `loki-values.yaml` and the comment naming the panel.
  - Add a test in `tests/grafana/test_grafana_dashboards.py` asserting panel layout, grid positions, queries, options equality, and mutation detections (pod back in selector, dropping `(?i)`, swapping panel y positions, leaving Row 18 at y=51).
- Manifests and dashboards are observable, so this change carries a spec delta for the `sre-service-dashboard` capability.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `sre-service-dashboard`: Layout and log filtering requirements for the *SRE / Service Performance & Logs* dashboard and Loki level detection configuration.

### Modified Capabilities

None.

## Impact

- Manifests / Dashboards: `k8s/monitoring/dashboards/sre-service.json`, `k8s/logging/loki-values.yaml`.
- Documentation: `k8s/README.md`.
- Tests: `tests/commands/k8s/test_k8s.py`, `tests/grafana/test_grafana_dashboards.py`.
- No new external ports, network egress, or secret requirements.

## Feasibility

- Loki 3.6+ defaults `discover_log_levels: true` under `limits_config`, which normalizes pod log levels (`warn`, `error`) and preserves Kubernetes event levels (`Warning`).
- Live tests on 2026-10-08 confirmed `sum by (detected_level) (count_over_time({namespace="devops"} | detected_level=~"(?i)(warn|warning|error|err|critical|fatal|panic)" [1h]))` returned only Warning, error, and warn lines.
- Moving `pod=~"$pod"` out of the stream selector into a LogQL filter pipeline matches structured metadata correctly when a pod is chosen.
- Loki query syntax accepted by Loki `/loki/api/v1/format_query`.

## Existing Tool Considered

Grafana covers the logs panel type on a Loki datasource, LogQL stream selectors and label filters including `detected_level` and `pod` filters, and dashboard layout. It lacks nothing in capability; the work is authoring the dashboard JSON in the repository and pinning Loki's `discover_log_levels`, which are configuration steps in this repository. No internal code is deleted.
