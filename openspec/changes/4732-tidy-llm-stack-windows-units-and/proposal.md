# Proposal: #4732

## Why
The LLM stack dashboard (`llm-stack.json`) gives wrong or noisy values (#4732). Its time series take each rate over a fixed `[5m]` or `[2m]` window, so a short peak goes away at a wide time range. Six breakdown panels add `Average (Mean)` and rolling lines to 4 to 6 entity lines. "GPU Memory Used" uses `decmbytes` for a value in MiB. "Requests per Virtual Model" and "Responses by Status Code" count the `/v1/systemone` route, which is not a model call. The cooldown and fallback panels are empty time series, Qdrant draws its error responses two times, and one Qdrant panel puts 2 collections and about 58,000 vectors on one axis.

## What Changes
- Each time series target of `llm-stack.json` takes its rate over `$__rate_interval`.
- "Calls in Flight per Deployment", "Requests per Deployment" and "GPU Power" keep only the entity lines and `Total (Sum)`. "GPU Utilisation", "GPU Memory Used" and "GPU Memory Utilization (%)" keep only the entity lines. The `Average (Mean)`, `Total Rolling Avg (30m)` and `Average Rolling Avg (30m)` targets and their overrides go.
- "GPU Memory Used" uses the unit `mbytes` (MiB).
- "Requests per Virtual Model" and "Responses by Status Code" select `route=~"/v1/(chat/completions|embeddings)"`, as `ai-spend.json` does.
- The cooldown and fallback panels become stats of `increase(...[$__range])`, named "Cooldowns per Deployment in Range" and "Fallbacks per Model Pair in Range". With no series they show "none recorded".
- "Qdrant Request Rate and Errors" keeps one target by status. A new stat "Qdrant Collections" shows the collection count, and "Qdrant Vectors per Collection" draws the vectors of each collection.
- The `dashboard-aggregate-lines` requirement no longer names `llm-stack.json`. The `llm-stack-dashboard` capability gets the new requirements. `k8s/README.md` says how the cooldown and fallback stats read before the first event.

The change fits one pull request: one dashboard, its tests and one README sentence.

## Capabilities
- `llm-stack-dashboard`: ADDED requirements for windows, lines, units, routes, counts in range and the Qdrant row.
- `dashboard-aggregate-lines`: MODIFIED requirement "Breakdown panels show properly wrapped sum and average lines", which no longer names `llm-stack.json`.

## Impact
- Grafana shows the new panels after Argo CD syncs the `grafana-stack-dashboards` ConfigMap. No code, setting or metric changes.
- `tests/grafana/test_grafana_dashboards.py` and `tests/commands/k8s/test_stack_dashboards.py` hold the new panels.

## Feasibility
- Routes: a Prometheus instant query on 2026-11-12, `round(sum by (route) (increase(litellm_proxy_total_requests_metric_total[24h])))`, gave `/v1/chat/completions` 3937, `/v1/embeddings` 1012 and `/v1/systemone` 205. The capture `tests/fixtures/metrics/litellm.yaml` gives the `route` label on `litellm_proxy_total_requests_metric_total`.
- Units: the NVIDIA DCGM field list gives `DCGM_FI_DEV_FB_USED` in MiB. Grafana's unit `mbytes` is mebibytes (IEC) and `decmbytes` is megabytes (SI), so 17,964 MiB showed as 18.0 GB.
- `$__rate_interval`: Grafana documents it as max(`$__interval` + scrape interval, 4 x scrape interval), so a rate always has 4 samples and follows the time range.
- Constant fallback: the issue asks for `or vector(0)` on the stats. `expression_violations` in `tests/commands/k8s/test_stack_dashboards.py` refuses a query of `llm-stack.json` that falls back to a constant, and `k8s/README.md` gives the reason: no data must not read as zero. So the stats use `noValue: "none recorded"`, as `otel-collector.json` does, and no query has a constant.
- Census of fixed windows in time series targets of `llm-stack.json`, counted with `re.findall(r"\[[^\]]*\]", expr)` on base: 20 targets with `[5m]` or `[2m]` (the issue counted 21), and 4 rolling targets with `[30m]` or `[30m:1m]`. After the change: 0, which `test_llm_stack_time_series_take_each_rate_over_the_rate_interval` holds.

## Existing Tool Considered
Built-in Grafana panel types (time series, stat), the `$__rate_interval` and `$__range` variables and plain PromQL cover the need. No new code. The change deletes the mean and rolling targets and their overrides in `llm-stack.json`.
