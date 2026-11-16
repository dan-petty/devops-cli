# Proposal: #5914

## Why

Issue #5914 records that the local-savings panels of `k8s/devops/dashboards/ai-spend.json` show values about 1000 times too high. On 2026-11-16 at 01:35Z, for 6 h, Projected 30-Day Run Rate showed $20,143 of savings. There are two causes:

- The dashboard constant `reference_price_usd_per_token` holds the prices of `gpt-4o` and `text-embedding-3-small` (2.5, 10 and 0.02 USD per million tokens). The owner values a local token at the hosted price of `qwen3.8:27b` (0.035 and 1.50 USD) and `qwen/qwen3-embedding-8b` (0.01 USD), the `ai.reference_model` and `ai.price_overrides` of the Service ConfigMap (#4241). The spend reports of the Service use these prices.
- The savings read devops-cli's own `devops_cli_ai_tokens_total{local="true"}`. Before #5874, hosted DeepSeek calls through the gateway had `local="true"` (#5867), so each range that holds those points counts them.

The owner requirement of 2026-11-16 also asks that Local Savings per Hour by Backend Server shows one series for each in-cluster backend and no series of the gateway, and that the spend-by-model panel names the hosted provider first.

## What Changes

- The constant holds 0.035 and 1.50 USD per million chat tokens and 0.01 and 0 USD per million embedding tokens. A test builds the pricing registry of the spend reports from `k8s/devops/configmap.example.yaml` and fails when a price of the dashboard differs.
- Each savings query reads the gateway's `litellm_input_tokens_metric_total` and `litellm_output_tokens_metric_total` with `api_provider` `ollama_chat` (chat) or `ollama` (embeddings). No savings query reads `devops_cli_ai_tokens_total`, so the old-label fallbacks of #2194 go too.
- The savings of each projection take the rate of the last 7 days, as its spend does.
- Local Hardware Savings Rate ($/hour) becomes Local savings: USD per hour, hourly bars of `increase(...[$__interval])`. The `[5m]` and `[1h]` lines go.
- Local Savings per Hour by Backend Server becomes Local savings by backend server: USD per hour: stacked hourly bars, one for each Kubernetes service. The query joins the tokens on `model_id` to the service name in the `api_base` of `litellm_deployment_total_requests_total`. An embedding deployment has no `api_base` there, so its model names its bar. The `[6h]` line goes.
- Spend by model: USD per hour becomes Spend by provider and model: USD per hour, with the legends `{{api_provider}}: {{model}}` and `{{provider}}: {{model}}`.
- promtool cases of the savings panels, a new record of the savings query against live Prometheus, and fixes to three test checks: a constant variable of a dashboard fills its cases, `$1` of `label_replace` is no Grafana variable, and a string of a query holds no window and no series.
- The change is a manifest that a consumer observes, so it has spec deltas. It fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: The AI spend dashboard holds the reference prices; The savings queries price every range and every token series; new requirements for the savings projections, the hourly savings bars, the backend names and the providers of the in-cluster deployments.
- `gateway-caller-telemetry`: The dashboard reads only gateway series that the gateway serves; The spend panels take gateway spend from the gateway; The hourly spend panels draw bars that follow the step; a new requirement that the spend panel names the provider first.

## Impact

- Manifest: `k8s/devops/dashboards/ai-spend.json`.
- Code comments and generated text: `src/devops_cli/config/defaults.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/docs/generator.py` (`docs/TELEMETRY.md`).
- Tests: `tests/prometheus/test_k8s_monitoring_dashboards.py`, `tests/prometheus/test_dashboard_queries.py`, `tests/grafana/test_grafana_dashboards.py`, `tests/commands/k8s/test_stack_dashboards.py`, `tests/fixtures/dashboard_queries/ai-spend.yaml`, `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml`.
- Documents: `k8s/README.md`.
- The savings no longer count a local call that does not go through the gateway. On 2026-11-16, devops-cli's series hold 209,314 such chat tokens in 30 d, all sent through the public route of the same gateway, which counts them.

## Feasibility

- Live Prometheus, read-only, on 2026-11-16: the gateway token counters carry `api_provider` (`ollama_chat` for `qwen3.8:27b`, `ollama` for `qwen3-embedding:0.6b`, `openrouter`, `anthropic`), `model` and `model_id`, with samples from 2026-10-17, so the 30-day retention is full.
- `litellm_deployment_total_requests_total` gives `api_base` `http://ollama-48gib-fast...` and `http://ollama-64gib-standard...` for the two chat `model_id`s, and no `api_base` for the two embedding deployments. No other LiteLLM series gives their `api_base`. Some series of the counter have no `api_base` or no `model_id`, and a join on all of them fails with "duplicate series for the match group", so the query selects `model_id!=""` and prefers the series with an `api_base`.
- For the 6 h to 01:35Z, the new query gives $0.149 of savings and the 30-day projection $31.99, where the old queries give $167.87 and $20,143. For 7 d to 03:00Z, the hourly bars add up to $7.621 and the bars by backend to $7.621, and the savings in range are $7.664 (0.6 %).

## Existing Tool Considered

The LiteLLM gateway (BerriAI/litellm, maintained) already exports the token counters and the deployment counter, and Prometheus already scrapes them. Grafana's bar panels, `$__interval` and PromQL `label_replace` do the rest, and the pricing registry of devops-cli already prices the reference models. The change builds no code. It deletes the `devops_cli_ai_tokens_total` savings queries with their old-label fallbacks, the `[5m]`, `[1h]` and `[6h]` savings lines, the genai-prices price of `gpt-4o` in the dashboard and the test that compared it.
