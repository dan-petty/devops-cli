# Tasks

## 1. One reference price for the local tokens of every process

- [x] 1.1 Write `test_two_processes_with_different_references_send_the_same_local_series` and `test_a_local_call_sends_its_tokens_as_local_and_no_price_of_its_own`, change the token assertions of the gateway, override and backend tests to read the `local` label in `tests/test_telemetry_instruments.py`, write `test_the_reference_price_rule_holds_the_genai_prices_price_of_each_default_reference` and `test_every_savings_query_prices_local_tokens_at_the_reference_price_rule` in `tests/test_k8s_monitoring_dashboards.py`, and verify that they fail on the base (`uv run devops ci test tests/test_telemetry_instruments.py tests/test_k8s_monitoring_dashboards.py`)
- [x] 1.2 Send `local` on `devops_cli_ai_tokens_total`, and delete `AI_LOCAL_COST_EQUIVALENT_USD_TOTAL`, `_emit_local_cost_equivalent` and their tests (`uv run devops ci test tests/test_telemetry_instruments.py`)
- [x] 1.3 Add the recording rule `devops_cli:ai_reference_price_usd_per_token` to `k8s/monitoring/prometheus-values.yaml`, and make the eight savings queries of `k8s/monitoring/dashboards/ai-spend.json` multiply the local tokens by it (`uv run devops ci test tests/test_k8s_monitoring_dashboards.py tests/test_telemetry_instruments.py tests/test_grafana_dashboards.py tests/test_k8s_monitoring_alerting.py`)
- [x] 1.4 Describe the query-time pricing in the telemetry part of `src/devops_cli/docs/generator.py`, `k8s/README.md` and `config.example.yaml`, and regenerate the documents (`uv run devops docs generate --sync-readme`, then `uv run devops docs check`)

## 2. A reference model with no price

- [x] 2.1 Write `test_an_unknown_reference_model_leaves_local_savings_unpriced_and_warns_once` and `test_devops_ai_cost_says_local_savings_are_unpriced_instead_of_printing_zero` in `tests/test_ai_spend_ledger.py`, `test_an_unpriced_reference_exposes_no_savings_gauge` in `tests/test_ai_spend_prometheus.py` and `test_config_show_warns_about_a_reference_model_that_genai_prices_does_not_know` in `tests/test_config_cmd.py`, and verify that they fail on the base (`uv run devops ci test tests/test_ai_spend_ledger.py tests/test_ai_spend_prometheus.py tests/test_config_cmd.py`)
- [x] 2.2 Add `PricingRegistry.price_reference`, make `ReferencePricing.cost` and the savings values of the report None for an unpriced reference, show `unpriced` in `devops ai cost`, leave the savings gauges out of the ledger exposition, and check both reference models in `devops config show` (`uv run devops ci test tests/test_ai_spend_ledger.py tests/test_ai_spend_prometheus.py tests/test_config_cmd.py`)
- [x] 2.3 Write `test_only_the_defaults_name_the_default_reference_model` in `tests/test_ai_spend_pricing.py`, make the `--reference-model` help name the setting, and regenerate the documents (`uv run devops ci test tests/test_ai_spend_pricing.py`, then `uv run devops docs generate --sync-readme`)

## 3. The pricing source of each request

- [x] 3.1 Write `test_an_unknown_hosted_model_is_priced_unknown_and_warns_once` in `tests/test_ai_spend_pricing.py`, `test_each_request_records_where_its_price_came_from` and `test_an_existing_ledger_gains_the_pricing_source_column` in `tests/test_ai_spend_ledger.py`, and verify that they fail on the base (`uv run devops ci test tests/test_ai_spend_pricing.py tests/test_ai_spend_ledger.py`)
- [x] 3.2 Return `RequestCost` from `PricingRegistry.calculate_request_cost`, delete `_check_override_cost` and `_calc_exact_genai_cost`, catch only `LookupError` and `ValueError` from genai-prices, warn once for each unpriced hosted model, store `pricing_source` in the ledger, and lower the swallowed-failures ceiling of `src/devops_cli/ai/spend/pricing.py` from 15 to 7 (`uv run devops ci test tests/test_ai_spend_pricing.py tests/test_ai_spend_ledger.py tests/test_ai_agent_capabilities.py`, then `uv run python -m tests.test_swallowed_failures_ratchet --lower`)

## Workflow follow-up

- Pending a person: confirm that the default reference models, `gpt-4o-mini` and `text-embedding-3-small`, price the AI spend dashboard. To price it at `gpt-4o`, change `DEFAULT_AI_REFERENCE_MODEL` and the chat prices of the recording rule together.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
