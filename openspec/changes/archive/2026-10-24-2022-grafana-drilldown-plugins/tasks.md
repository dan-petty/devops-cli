# Tasks

## 1. Pin the Drilldown apps

- [x] 1.1 Write `test_grafana_pins_each_drilldown_app_at_its_release_for_grafana_13` in `tests/test_k8s_monitoring_integration.py`, and verify that `uv run devops ci test tests/test_k8s_monitoring_integration.py` fails on the base and names the four apps
- [x] 1.2 Pin the four apps at 3.0.0 in the `plugins` value of `k8s/monitoring/grafana-values.yaml`, and verify that `uv run devops ci test tests/test_k8s_monitoring_integration.py tests/test_k8s_monitoring_alerting.py tests/test_k8s_argocd_apps.py tests/test_k8s.py tests/test_third_party_telemetry.py tests/test_k8s_tempo.py` passes
- [x] 1.3 Render the chart with `helm template grafana grafana-community/grafana --version 14.0.1 -f k8s/monitoring/grafana-values.yaml`, and verify that the `grafana` ConfigMap holds the four pins in its `plugins` key and that the Deployment sets `GF_PLUGINS_PREINSTALL_SYNC` from that key
- [x] 1.4 Run `uv run devops openspec check`, and verify that it passes

## Workflow follow-up

- Renovate proposes a new release of each pinned Grafana plugin, so that a pin does not stay behind: moved to #2054.
- Pending a person: after Argo CD syncs Grafana, open Logs, Metrics, Traces and Profiles under Drilldown, and verify that each app opens and that `GET /api/plugins?type=app` lists each of the four apps at 3.0.0.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
