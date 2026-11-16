# Tasks

## 1. Price the local savings at the reference model from the gateway counters

Kind: behavior. Reads: `k8s/devops/dashboards/ai-spend.json`, `k8s/devops/configmap.example.yaml`, `k8s/llm/gateway/config.yaml`, `tests/fixtures/metrics/litellm.yaml`. Changes: `k8s/devops/dashboards/ai-spend.json`, `tests/prometheus/test_k8s_monitoring_dashboards.py`, `tests/prometheus/test_dashboard_queries.py`, `tests/grafana/test_grafana_dashboards.py`, `tests/commands/k8s/test_stack_dashboards.py`, `tests/fixtures/dashboard_queries/ai-spend.yaml`, `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml`.

- [x] 1.1 Add the tests: the constant against the pricing registry of the ConfigMap template, the owner prices, the 6 savings queries on the gateway token counters, the 7-day savings projections, the hourly savings bars, the backend names, the providers of the in-cluster deployments and the provider-first legends. Add the promtool cases of the savings panels, record the savings query again against live Prometheus, and fix the checks for a constant variable, `$1` and the strings of a query
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py tests/prometheus/test_dashboard_queries.py tests/grafana/test_grafana_dashboards.py tests/commands/k8s/test_stack_dashboards.py` fails on the base
- [x] 1.2 Change the constant, the savings queries, the two hourly savings panels and the spend panel by provider of `k8s/devops/dashboards/ai-spend.json`, with their titles, legends and descriptions
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py tests/prometheus/test_dashboard_queries.py tests/grafana/test_grafana_dashboards.py tests/commands/k8s/test_stack_dashboards.py`
- [x] 1.3 Lint the dashboard
  - Verification: `$ uv run devops grafana dashboards lint k8s/devops/dashboards/ai-spend.json`

## 2. Documents

Kind: other. Reads: `k8s/README.md`, `docs/TELEMETRY.md`. Changes: `k8s/README.md`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`, `src/devops_cli/config/defaults.py`.

- [x] 2.1 Tell in `k8s/README.md` and in the generated `docs/TELEMETRY.md` where the savings take their tokens and prices, and fix the comment of `DEFAULT_AI_REFERENCE_MODEL`
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: promtool gives $48 of savings for 24 h of fixture series worth $2 an hour, $1,440 for the 30-day projection, and $1, $0.75 and $0.25 for the three backends of one hour.
- Group 1: live for 7 d, the hourly savings bars and the bars by backend add up to within 1 % of the savings in range.

## Workflow follow-up

- #5784 asked for step windows in the old savings queries. This change replaces those queries, and the projections take a `[7d]` baseline.
- #2202 asked to drop the old-label fallbacks of the savings queries after 2026-11-23. This change removes the queries that held them.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
