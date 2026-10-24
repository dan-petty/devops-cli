# Task: The Spend Series Exists at $0, a Gateway Call Is Local or Hosted by the Backend That Served It, and the Ledger Exposition Has Its Own Names (#1631)

**Issue**: [#1631](https://github.com/dan-petty/devops-cli/issues/1631)
**Scope**: scope/ai, scope/telemetry
**Feasibility**: Checked on 2026-10-24 at `origin/main` 64e74dd2, read-only. In live Prometheus, `devops_cli_ai_spend_usd_total` had no series in 60 days. `devops_cli_info`, `devops_cli_uptime_seconds` and `devops_cli_ai_active_servers` also had no series, so nothing scrapes the `/metrics` endpoint of `devops serve`. Over 30 days, `devops_cli_ai_requests_total` had two `server` values for the one gateway: the public host from workstations and the in-cluster Service from roadmap-service. The gateway runs LiteLLM 1.103.0. In its source, `get_custom_headers` (`proxy/common_request_processing.py`) sets `x-litellm-model-api-base` from the `api_base` hidden parameter of the reply, and `get_api_base` (`litellm_core_utils/llm_response_utils/get_api_base.py`) gives the `api_base` of the route, or a default URL for some providers. An offline probe in the gateway pod gave `https://api.openai.com` for `openai/gpt-4o`, an API URL for `groq`, `deepseek`, `mistral` and `gemini` routes, and no value for `anthropic`, `openrouter` and `bedrock` routes that have no `api_base`. LiteLLM sends no header for an empty value. Each route in `k8s/llm/gateway/configmap.yaml` sets `api_base` to an in-cluster Ollama Service. The OpenTelemetry SDK exports a counter point of 0 after an add of 0.

## Description
Four defects made the AI spend data unreliable. A request that cost nothing added nothing to the spend counter. Thus the series did not exist, and three dashboard targets showed "No data", which a broken pipeline also shows. The host that a call went to decided if the call was spend or local savings. Thus a hosted route behind the local gateway would count as savings. A custom price for a local model booked the call as spend and removed it from the savings. The ledger exposition used the names of the OTLP counters, so a dashboard sum by name would add the lifetime ledger to them.

Now each request that a model answers adds to the spend counter, and a local request adds 0. The backend that the gateway names in its reply decides if the call is local. A local call costs nothing, also when it has a custom price. The ledger exposition has gauges, and the name of each gauge starts with `devops_cli_ai_ledger_`.

## Key Changes
- **Spend counter** (`ai/spend/ledger.py`). `track_request_spend` sends one spend point for each request that the response cache did not answer. The value is 0 for a local request. A cached reply sends no spend point.
- **Serving backend** (`ai/spend/pricing.py`, `ai/spend/ledger.py`). `is_local`, `PricingRegistry.get_pricing` and `PricingRegistry.calculate_request_cost` take `served_by`. When the reply names a backend, that backend decides. When it names no backend, the provider and the server decide, as before. `track_request_spend` gives `served_by` to the cost and to the local savings. The report of `devops ai cost` counts local usage by server, provider and serving backend, and a server is local only when each backend that served its calls is local. The `_is_local` alias is removed.
- **Custom prices** (`ai/spend/pricing.py`, `commands/ai_cost.py`). The local check is before the custom price check, so a custom price applies only to hosted calls. The help of `devops ai cost set-price` says this.
- **Ledger exposition** (`ai/spend/prometheus.py`). Each family is a gauge, because each value is a snapshot of the ledger over the date range of the report. The families are `devops_cli_ai_ledger_active_servers`, `_active_models`, `_local_cost_equivalent_usd`, `_counterfactual_spend_usd`, `_counterfactual_savings_usd`, `_hardware_cost_usd`, `_hardware_payoff_percentage`, `_hardware_net_value_usd`, `_server_spend_usd`, `_spend_usd`, `_requests` and `_tokens`. The tokens gauge has `prompt` and `completion` samples and no `total` sample. `devops ai cost --format prometheus`, `devops ai cost report --format prometheus`, `devops ai cost prometheus` and the `/metrics` endpoint of `devops serve` show it.
- **Dashboards** (`k8s/monitoring/dashboards/ai-spend.json`, `devops-cli.json`). In "Spend per Hour by Backend Server" and "AI Spend Rate by Server ($/hr)", the targets that group by labels fall back to the requests that a model answered, grouped the same way, times 0. The ungrouped 6 h average falls back to `vector(0)`.
- **Docs**. `docs/TELEMETRY.md`, `docs/CLI_REFERENCE.md` and `docs/commands/ai.md` are generated again from the instrument description and the command help.

## Decisions
- The exposition stays, with new names, and is not deleted. `devops ai cost --format prometheus` and `devops ai cost report --format prometheus` print it, and their tests read it.
- A grouped spend target does not get `or vector(0)`. `test_a_grouped_query_adds_no_unlabelled_zero_series` forbids it, because `vector(0)` adds a 0 line with no labels next to the real series (#692). The target falls back to its requests times 0, as "Command Error Share" does. Each backend that served requests then shows $0 with its labels.
- A custom price for a local call is not recorded. `ai.hardware_cost_usd` and the hardware payoff report hold the cost of the local hardware.
- A gateway route must set `api_base`, because LiteLLM names no backend for some routes without it. `test_gateway_egress_admits_all_backends_in_configmap` already fails for a route that has no in-cluster `api_base`.
- `telemetry/tracer.py` does not change: the SDK exports an add of 0.

## Acceptance Criteria
- [x] A local request that the cache did not answer sends one spend point of 0 next to its savings: `test_local_ai_calls_emit_equivalent_spend_instrument`.
- [x] Each target of the spend counter in `ai-spend.json` and `devops-cli.json` falls back to 0, in one structural check over all targets: `test_every_spend_query_shows_zero_when_no_spend_series_matches`.
- [x] A gateway call that a local backend served counts as local, also when no setting names the gateway host. A call that a hosted API served counts as spend. With no backend named, the host decides: `test_a_gateway_call_is_spend_or_savings_by_the_backend_that_served_it`, `test_a_gateway_call_is_local_by_the_backend_that_served_it`, `test_a_gateway_call_is_priced_by_the_backend_that_served_it` and `test_ai_calls_count_requests_tokens_and_spend_by_backend`.
- [x] The report counts the local usage of a gateway by the backend that served each call: `test_the_report_counts_a_gateway_call_as_local_by_the_backend_that_served_it`.
- [x] A custom price for a local server or model leaves the call in local savings: `test_a_custom_price_leaves_a_local_call_at_no_cost`, `test_a_price_override_leaves_a_local_call_in_local_savings` and `test_embedding_cost_of_a_local_model_is_zero_whatever_its_custom_price`.
- [x] No name that the ledger exposition sends is the name of an instrument in `telemetry/instruments.py`, each family is a gauge, and no sample has `type="total"`: `test_the_ledger_exposition_shares_no_name_with_an_otlp_instrument` and `test_server_metrics_endpoint_includes_ai_spend`.
- [x] The three changed targets run in live Prometheus and return series of 0, with labels where they group, for hours that had requests and no spend.
- Pending a person: decide if a custom price for a local model must be recorded as a separate local running cost. This change does not record it.
- Pending a person: one day after the deploy, run `sum by (server, backend, provider) (increase(devops_cli_ai_spend_usd_total[24h]))` in Grafana Explore. Each backend that served a request on that day shows a series with the value 0.

## Not in this item
- One `server` value for each configured gateway: #1110.
- One reference price for each kind of request, and a warning for an unknown model or reference: #1672.
- Price a hosted gateway call at the deployment model that the gateway names in `x-litellm-model-name`, not at the name of the route, which genai-prices does not know: moved to #2031.
