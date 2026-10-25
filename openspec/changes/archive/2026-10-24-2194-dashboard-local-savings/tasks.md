# Tasks

## 1. One reference model, gpt-4o

- [x] 1.1 Write `test_the_dashboard_holds_the_genai_prices_price_of_each_default_reference` in `tests/test_k8s_monitoring_dashboards.py`, and `test_the_reference_model_check_finds_the_model_only_as_a_reference` in `tests/test_ai_spend_pricing.py`, and verify that the first fails on the base (`uv run devops ci test tests/test_k8s_monitoring_dashboards.py tests/test_ai_spend_pricing.py`)
- [x] 1.2 Set `DEFAULT_AI_REFERENCE_MODEL` to `gpt-4o`, and make `test_only_the_defaults_name_the_default_reference_model` find a literal only where it names a reference model (`uv run devops ci test tests/test_ai_spend_pricing.py tests/test_ai_spend_ledger.py tests/test_ai_spend_prometheus.py tests/test_ai_spend_cli.py tests/test_ai_spend_payoff.py tests/test_config_cmd.py`)
- [x] 1.3 Show the new default in `config.example.yaml`, and regenerate the documents (`uv run devops docs generate --sync-readme`, then `uv run devops docs check`)

## 2. The dashboard prices every range and every series

- [x] 2.1 Record the answers of the live Prometheus in `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml`, write `test_each_savings_query_prices_all_local_tokens_at_the_dashboard_prices`, `test_local_cloud_savings_in_range_gives_the_priced_total_of_the_recorded_series` and `test_the_records_hold_each_kind_of_series_and_a_range_before_the_price_rule` in `tests/test_k8s_monitoring_dashboards.py`, and verify that the first two fail on the base (`uv run devops ci test tests/test_k8s_monitoring_dashboards.py`)
- [x] 2.2 Add the constant `reference_price_usd_per_token` to `k8s/monitoring/dashboards/ai-spend.json`, make the eight savings queries multiply the local tokens of every kind of token series by it, delete the recording rule `devops_cli:ai_reference_price_usd_per_token` from `k8s/monitoring/prometheus-values.yaml`, and delete the tests of the rule (`uv run devops ci test tests/test_k8s_monitoring_dashboards.py tests/test_telemetry_instruments.py tests/test_grafana_dashboards.py tests/test_k8s_monitoring_alerting.py tests/test_stack_dashboards.py`)
- [x] 2.3 Describe the dashboard prices in the telemetry part of `src/devops_cli/docs/generator.py`, the description of `devops_cli_ai_tokens_total`, `k8s/README.md` and the panel descriptions, and regenerate the documents (`uv run devops docs generate --sync-readme`, then `uv run devops docs check`)

## Workflow follow-up

- Remove the mapping of token series without the `local` and `operation` labels from the savings queries, the record and its tests when `count(last_over_time(devops_cli_ai_tokens_total{local=""}[30d]))` is empty, after about 2026-11-23: #2202.
- Pending a person: after Argo CD applies the dashboard, set the time range of the AI spend dashboard to 2026-10-01 to 2026-10-21 and check that "Local Cloud Savings in Range" shows about $423.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
