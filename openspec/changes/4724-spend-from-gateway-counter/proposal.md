# Proposal: #4724

## Why

Issue #4724 records that the spend panels of `k8s/devops/dashboards/ai-spend.json` show too little spend. They read `devops_cli_ai_spend_usd_total`, which a Job pod sends only a few times an hour. On 2026-11-16, for 6 h, the gateway counter `litellm_spend_metric_total` gives $1.23 and devops-cli's counter gives $0.67. A `rate(...[5m])` window holds no sample of a sparse series, so the spend rate line shows only the Service. A `rate(...[1h])` window sometimes holds two samples and extrapolates, so the rolling line has spikes. The projections follow the range picker, and the coverage stat shows the request coverage, not the spend coverage.

## What Changes

- Cloud Spend in Range (was Direct Cloud Spend in Range) adds `litellm_spend_metric_total` and `devops_cli_ai_spend_usd_total{provider!="gateway"}`, each with a fallback to 0.
- The spend target of Projected 30-Day, 90-Day and 1-Year Run Rate reads the spend rate of the last 7 days (`[7d]`) from the same two counters. The savings target stays as it is.
- Spend: USD per hour (was AI Spend Rate ($/hour)) draws bars of `increase(...[$__interval])` with a Min interval of 1h. The `[5m]` line and the `[1h]` rolling line go.
- Spend by model: USD per hour (was Spend per Hour by Backend Server) draws stacked bars by the gateway's `model` and `api_provider`, and by devops-cli's `model` and `provider` for direct calls. A model with no spend has no bar. The `[6h]` rolling line goes.
- devops-cli Coverage of Gateway Spend (was devops-cli Coverage of Gateway Requests) divides devops-cli's `provider="gateway"` spend by the gateway's spend counter. It shows red under 95 % and over 105 %.
- `tests/fixtures/dashboard_queries/ai-spend.yaml` holds promtool cases of these queries.
- The change is a manifest that a consumer observes, so it has a spec delta. It fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `gateway-caller-telemetry`: The spend panels take gateway spend from the gateway; A spend projection reads the last 7 days; The hourly spend panels draw bars that follow the step; The dashboard shows the gateway's attempts, callers and coverage.

## Impact

- Manifest: `k8s/devops/dashboards/ai-spend.json`.
- Tests: `tests/fixtures/dashboard_queries/ai-spend.yaml` (new), `tests/prometheus/test_k8s_monitoring_dashboards.py`, `tests/grafana/test_grafana_dashboards.py`, `tests/telemetry/test_telemetry_instruments.py`.
- Documents: `k8s/README.md`.
- The local-savings queries do not change: #5914 changes their price and source, and #5784 their windows. The request, token and slot-wait panels and the spend panels of `devops-ai-rag.json` go to #5922.

## Feasibility

- Live Prometheus on 2026-11-16, 6 h to 02:00Z: `sum by (model, api_provider, requested_model) (increase(litellm_spend_metric_total[6h]))` gives $1.17 for `deepseek/deepseek-v4.1-flash-1017:floor` on `openrouter` and $0 for the two local models.
- `devops_cli_ai_spend_usd_total{provider!="gateway"}` has no spend in 30 d, so today the gateway counter holds all the spend.
- The new in-range query gives $1.23 for 6 h, where the old query gives $0.67. The 6 hourly bars add up to $1.234. For 7 d, the 169 hourly bars add up to $142.44, and the 7 d increase is $142.04 (0.3 %).
- The new coverage stat gives 0.544 for 6 h and 0.775 for 7 d.
- `tests/fixtures/metrics/litellm.yaml` holds `litellm_spend_metric_total` with the labels `model` and `api_provider`. The gateway ServiceMonitor drops `user_agent` and `client_ip` (#4545), so no query reads them.

## Existing Tool Considered

The LiteLLM gateway (BerriAI/litellm, maintained) already exports `litellm_spend_metric_total`, and Prometheus already scrapes it. Grafana's bar panels and `$__interval` do the rest. The change builds no code. It deletes the `[5m]`, `[1h]` and `[6h]` spend queries and the per-backend `or ... * 0` fallback of the spend panels.
