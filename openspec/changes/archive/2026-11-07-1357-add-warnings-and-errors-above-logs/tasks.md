# Tasks

## 1. Pin discover_log_levels in Loki Helm values

Reads: `k8s/logging/loki-values.yaml`. Changes: `k8s/logging/loki-values.yaml`.

- [x] 1.1 In `k8s/logging/loki-values.yaml`, set `discover_log_levels: true` under `loki.limits_config` with a comment naming the *Warnings & Errors (Loki)* panel that depends on it
  - Verification: `git grep -n "discover_log_levels: true" k8s/logging/loki-values.yaml` matches and comments name `Warnings & Errors (Loki)`

## 2. Update SRE service dashboard layout and log panels

Reads: `k8s/monitoring/dashboards/sre-service.json`. Changes: `k8s/monitoring/dashboards/sre-service.json`.

- [x] 2.1 Add panel 21 *Warnings & Errors (Loki)* at `h: 8, w: 24, x: 0, y: 39` above panel 12 with query `{namespace=~"$namespace"} | pod=~"$pod" | detected_level=~"(?i)(warn|warning|error|err|critical|fatal|panic)"` and panel 12's options
  - Verification: `uv run devops grafana dashboards lint k8s/monitoring/dashboards/sre-service.json` reports zero errors and zero warnings
- [x] 2.2 Update panel 12 *Live Service Logs (Loki)* to `y: 47, h: 12`, change query to `{namespace=~"$namespace"} | pod=~"$pod"`, and remove "service" from description
  - Verification: `uv run devops grafana dashboards lint k8s/monitoring/dashboards/sre-service.json` reports zero errors and zero warnings
- [x] 2.3 Shift Row 18 to `y: 59`, flamegraph 19 to `y: 60`, and flamegraph 20 to `y: 72`
  - Verification: `uv run devops grafana dashboards lint k8s/monitoring/dashboards/sre-service.json` reports zero errors and zero warnings

## 3. Update dashboard documentation in k8s README

Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [x] 3.1 Update `k8s/README.md` to use the real title *SRE / Service Performance & Logs* and list both log panels
  - Verification: `uv run devops ci docs` passes

## 4. Test suite for Loki settings, dashboard structure, and mutation assertions

Reads: `tests/commands/k8s/test_k8s.py`, `tests/grafana/test_grafana_dashboards.py`. Changes: `tests/commands/k8s/test_k8s.py`, `tests/grafana/test_grafana_dashboards.py`.

- [x] 4.1 Add test in `tests/commands/k8s/test_k8s.py` verifying `discover_log_levels: true` and comment in `k8s/logging/loki-values.yaml`
  - Verification: `uv run devops ci test tests/commands/k8s/test_k8s.py` passes
- [x] 4.2 Add test in `tests/grafana/test_grafana_dashboards.py` asserting panel positions, queries, options, relationship, and mutation detection
  - Verification: `uv run devops ci test tests/grafana/test_grafana_dashboards.py` passes

## Workflow follow-up

- Pending a person: after merge and Argo CD sync of monitoring, open the dashboard with namespace `devops`, pod "All", over the last hour. Verify the lower panel lists every line and the top panel lists only warnings and errors.
- Pending a person: open the top panel in Explore over a fixed 1h range; verify the volume histogram shows only warn/warning/error levels.
- Pending a person: select a specific pod with warnings; verify both panels show only that pod's lines and are not empty.
