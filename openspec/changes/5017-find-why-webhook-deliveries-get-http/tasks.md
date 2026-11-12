# Tasks

## 1. The gauge of failed deliveries (behavior)

- [x] 1.1 Write failing tests: a page with two 403 answers sets the gauge to 2, the hooks add by code, a code goes to 0, a refused read raises, the metrics row sets the gauge, and the token asks for `repository_hooks: read`
  - Verification: `$ uv run devops ci test tests/github/test_hook_deliveries.py tests/roadmap/test_roadmap_run_metrics.py tests/github/test_github_app_identity.py`
- [x] 1.2 Read the hooks and their deliveries in the metrics row, set the gauge, and ask the token for `repository_hooks: read`
  - Verification: `$ uv run devops ci test tests/github/test_hook_deliveries.py tests/roadmap/test_roadmap_run_metrics.py tests/github/test_github_app_identity.py`

## 2. The alert (behavior)

- [x] 2.1 Write the promtool cases of `RoadmapServiceWebhookDeliveriesFailed` and the rule test of the group
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] 2.2 Add the rule to the group `roadmap-service-webhooks`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py tests/telemetry/test_telemetry_instruments.py`

## 3. Documents

- [x] 3.1 Name the edge check in `k8s/README.md` (setup steps 1, 6 and 12, Webhook route, Alerts), and amend ADR 0015
  - Verification: `$ uv run devops ci docs`
