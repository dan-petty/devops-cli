# Tasks

## 1. Drop the fallback from the savings queries and their record

Kind: manifest. Reads: `tests/prometheus/test_k8s_monitoring_dashboards.py`, `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml`. Changes: `k8s/devops/dashboards/ai-spend.json`, `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml`, `tests/prometheus/test_k8s_monitoring_dashboards.py`.

- [ ] 1.1 `test_each_savings_query_prices_all_local_tokens_at_the_dashboards_prices` in `tests/prometheus/test_k8s_monitoring_dashboards.py`, which fails with all 8 queries listed until each one drops its fallback selector, and then `test_local_cloud_savings_in_range_gives_the_priced_total_of_the_recorded_series` over the record in `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py` fails on the base
- [ ] 1.2 In `tests/prometheus/test_k8s_monitoring_dashboards.py`, extend the guard first: set `LOCAL_TOKEN_SELECTORS` to the two `local="true"` selectors, add `FALLBACK_SELECTORS = ('local=""', 'provider="gateway", server!="cache"')`, and make `_misses_a_local_token_or_the_price` return true when a query holds a fallback selector or a `label_replace`, in place of its `"operation", "chat", "", ""` clause; `test_each_savings_query_prices_all_local_tokens_at_the_dashboards_prices` then fails with the 8 queries listed, and its docstring loses the sentence about the series from before the labels. Then rewrite each of the 8 savings `expr` of `k8s/devops/dashboards/ai-spend.json` at lines 145, 349, 408, 467, 660, 669, 716 and 725 so that it keeps its own window and its own tail, but drops the `label_replace` and every `or increase(devops_cli_ai_tokens_total{local="", provider="gateway", server!="cache", ...})` disjunct, and sums each operation branch `by (operation, type)`. The range panel becomes `sum((sum by (operation, type) (increase(devops_cli_ai_tokens_total{local="true", operation!="embeddings"}[$__range])) or sum by (operation, type) (increase(devops_cli_ai_tokens_total{local="true", operation="embeddings"}[$__range]))) * on (operation, type) group_left () (${reference_price_usd_per_token:raw})) or vector(0)`; the other seven follow it with `rate(` and `[5m]`, `[1h]` or `[6h]` where they hold one, and the backend panel keeps its `sum by (server, backend, provider)`. Delete the fallback sentence from the descriptions at lines 95, 625 and 680. In `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml`, write `expr` as the new panel query, delete the key of the deleted price rule and the record that ends at 2026-10-22, keep the record that ends at 2026-10-24T22:00:00Z with only its four `local="true"` series, and set its `result` to their priced total at the dashboard constant; delete `test_the_records_hold_each_kind_of_series_and_a_range_before_the_price_rule` and update the comments that describe the old label sets
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py` passes

## 2. Read one label in the savings test helpers

Kind: other. Reads: `tests/prometheus/test_k8s_monitoring_dashboards.py`. Changes: `tests/prometheus/test_k8s_monitoring_dashboards.py`.

- [ ] 2.1 In `tests/prometheus/test_k8s_monitoring_dashboards.py`, make `_is_local` return `labels.get("local") == "true"` and make `_priced_total` read `point["labels"]["operation"]` with no default, then drop the fallback text from their docstrings, from the module comment at lines 90 to 92, and from the docstring of `test_local_cloud_savings_in_range_gives_the_priced_total_of_the_recorded_series`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py` passes

## 3. Drop the fallback text from the docs

Kind: other. Reads: `k8s/README.md`, `src/devops_cli/docs/generator.py`. Changes: `k8s/README.md`, `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`.

- [ ] 3.1 In `k8s/README.md`, rewrite the AI spend dashboard paragraph so that it says the savings queries read `devops_cli_ai_tokens_total{local="true"}` only, and delete the sentence that says to remove the mapping when `count(last_over_time(devops_cli_ai_tokens_total{local=""}[30d]))` is empty. In `src/devops_cli/docs/generator.py`, delete the two sentences about a series from before the `local` and the `operation` label from the telemetry paragraph at lines 1067 to 1069, then regenerate `docs/TELEMETRY.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops docs check` passes
- [ ] 3.2 Edit `k8s/README.md` and `src/devops_cli/docs/generator.py`, then regenerate `docs/TELEMETRY.md` with `uv run devops docs generate`. Update `src/devops_cli/telemetry/instruments.py`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: The check query above returns no series (record the date and output in the PR)., The query needs a network to the cluster Prometheus, and no runner has one. A person runs `uv run devops prometheus query 'count(last_over_time(devops_cli_ai_tokens_total{local=""}[30d]))'` after 2026-11-23 and records the date and the empty output, and the change starts only after it returns no series.
- Group 1: The savings queries name no series without `local`, and the dashboard tests pass with the record of the current label set only.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
