# Tasks

## 1. The linter reads an expression target by its expression

Kind: behavior. Changes: `tests/grafana/test_grafana_dashboards.py`, `src/devops_cli/grafana/schema.py`, `src/devops_cli/grafana/linter.py`, `src/devops_cli/config/constants.py`.

- [x] 1.1 Write the failing tests: a target of datasource type `__expr__` with a filled `expression` passes the lint, an empty one is an error, and a generated target has no `expression` key.
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py`
- [x] 1.2 Add the optional field `expression` to `Target`, and check it in place of `expr` for a target of the expression datasource.
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py`

## 2. The gateway database is scraped, watched and shown

Kind: behavior. Changes: `tests/gate/k8s_checks/gateway_database.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/llm_gateway_db_tests.yaml`, `tests/prometheus/test_k8s_monitoring_dashboards.py`, `tests/commands/k8s/test_k8s_mattermost.py`, `k8s/llm/gateway-db.yaml`, `k8s/llm/gateway/config.yaml`, `k8s/monitoring/networkpolicy.yaml`, `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/dashboards/`, `k8s/mattermost/cloudnative-pg-values.yaml`.

- [x] 2.1 Write the failing checks and tests: the PodMonitor and the 9187 rules, the three rules with their promtool cases and README rows, the ConfigMap `grafana-database-dashboards`, the chart dashboard off, and the 30-day spend-log retention.
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py tests/prometheus/test_k8s_monitoring_dashboards.py tests/commands/k8s/test_k8s_mattermost.py`
- [x] 2.2 Add the PodMonitor and the ingress rule to `k8s/llm/gateway-db.yaml`, and port 9187 to the egress of `monitoring` to namespace `llm`.
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 2.3 Add group `llm-gateway-db` to `k8s/monitoring/prometheus-values.yaml`.
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] 2.4 Copy the upstream CloudNativePG dashboard to `k8s/monitoring/dashboards/cloudnative-pg.json` with one space of indentation and without its empty target, add its generator, and turn off the chart's dashboard.
  - Verification: `$ uv run devops grafana dashboards lint k8s/monitoring/dashboards`
- [x] 2.5 Set `maximum_spend_logs_retention_period` to `30d` in the gateway config.
  - Verification: `$ uv run devops ci --check --only k8s`

## 3. Documents

Kind: documents. Changes: `k8s/README.md`.

- [x] 3.1 Describe the scrape, the rules, the dashboard and the spend-log retention in `k8s/README.md`.
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
