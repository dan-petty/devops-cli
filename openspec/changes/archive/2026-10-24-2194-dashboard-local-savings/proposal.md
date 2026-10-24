# Proposal

## Why

Issue #2194: the Grafana dashboard "AI Spend & LLM Usage Telemetry" (`k8s/monitoring/dashboards/ai-spend.json`, uid `ai-spend-telemetry`) showed $0 local savings for 2026-10-01 to 2026-10-22. Prometheus holds the tokens of that range, and `devops ai cost` prices them. There are three causes:

- Each savings query multiplied the local tokens by the recording rule `devops_cli:ai_reference_price_usd_per_token`. A recording rule has samples only from its first evaluation (2026-10-24T05:21Z). Thus a range that ended before that time had no price to multiply by.
- Each savings query selected `local="true"` and joined on `operation`. The token series from before #1672 have no `local` label, and the series from before #1623 have no `operation` label. Thus no token of that range matched.
- The rule priced chat tokens at `gpt-4o-mini` ($0.15 and $0.60 for each million prompt and completion tokens), the default `DEFAULT_AI_REFERENCE_MODEL`. The owner's `config.yaml` sets `ai.reference_model: gpt-4o` ($2.50 and $10), and `devops ai cost` prices at it. Thus the dashboard and the CLI report priced at two models.

## What Changes

- `DEFAULT_AI_REFERENCE_MODEL` in `src/devops_cli/config/defaults.py` becomes `gpt-4o`, the owner's choice. `text-embedding-3-small` stays the default embedding reference. `config.example.yaml` and the generated configuration reference show the new default.
- The AI spend dashboard gets the hidden constant `reference_price_usd_per_token`. Its value is a PromQL vector with one price for each operation and token type: genai-prices' price of the default reference model of the operation, written as USD per million tokens. It is the one copy of each price in git.
- The eight savings queries multiply the local tokens by `${reference_price_usd_per_token:raw}` on operation and token type. They read no series other than `devops_cli_ai_tokens_total`, so every range in the retention window is priced.
- The savings queries count the series from before the labels. A series without `local` is local when its provider is `gateway` and its server is not `cache`. Chat is every operation other than `embeddings`, so a series without `operation` is chat.
- The recording rule `devops_cli:ai_reference_price_usd_per_token` and its group are deleted from `k8s/monitoring/prometheus-values.yaml`.
- The test that keeps the default reference model literal in `config/defaults.py` finds a literal only where it names a reference model. gpt-4o is also the default of settings that are no reference, such as the tokenizer model of `context_budget.py`.
- A manifest and the value of a setting change, so the change has a spec delta. It removes the requirement of the recording rule and adds the requirement of the dashboard prices.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: the AI spend dashboard, not a recording rule, holds the reference prices, and it prices the token series from before the `local` and `operation` labels.

## Impact

- Code: `src/devops_cli/config/defaults.py`, the telemetry part of `src/devops_cli/docs/generator.py` and the description of `devops_cli_ai_tokens_total` in `src/devops_cli/telemetry/instruments.py`.
- Manifests: `k8s/monitoring/dashboards/ai-spend.json` and `k8s/monitoring/prometheus-values.yaml`.
- Documents: `k8s/README.md`, `config.example.yaml`, `docs/CONFIGURATION.md` and `docs/TELEMETRY.md`.
- Tests: `tests/test_k8s_monitoring_dashboards.py`, `tests/test_ai_spend_pricing.py`, `tests/test_telemetry_instruments.py`, and the new record `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml`.
- `devops ai cost` prices at gpt-4o when `ai.reference_model` is not set. The owner's configuration already sets gpt-4o, so its reports do not change.

## Feasibility

- Live Prometheus, read-only through the Grafana MCP server on 2026-10-24: `sum by (local, operation, provider, server, type) (increase(devops_cli_ai_tokens_total[21d]))` at 2026-10-22T00:00Z gave 136,084,728 prompt and 5,312,178 completion tokens for the workstation and 6,804,315 and 1,268,420 for the in-cluster Service. No series had a `local` or an `operation` label. The query of the panel on main gave 0 for that range.
- `min_over_time(timestamp(devops_cli:ai_reference_price_usd_per_token)[3d:1m])` gave 2026-10-24T05:21:33Z, the first sample of the rule.
- In 45 days, every series of `devops_cli_ai_tokens_total` has the provider `gateway`. The last sample without `local` was at about 2026-10-24T00:28Z. The Deployment `roadmap-service`, the other sender, has 0 replicas.
- Each `model` of `k8s/llm/gateway/config.yaml` is an `ollama/` or `ollama_chat/` model with an `api_base` at an in-cluster Ollama Service, and `store_model_in_db: false` stops models that the file does not name. In each of the 13 versions of the gateway configuration in git since 2026-09-15 (`k8s/llm/gateway/configmap.yaml` before #2033), each model has an `api_base` at an in-cluster Service (`*.svc.cluster.local`), and each version sets `store_model_in_db: false`. The `openai/` models of the older versions use the OpenAI protocol to in-cluster vLLM and Ollama Services, with `api_key: none`. Thus the gateway served only local models in the whole retention window.
- #1623 (commit 4bb052c6) says that the spend ledger and the AI counters did not record embedding requests before it. Thus a token series without `operation` is a chat series.
- The new query, run read-only in Prometheus 3.15.0 through `kubectl exec` and the Grafana MCP server, gave $423.03 for 2026-10-01 to 2026-10-22 (workstation $393.33, in-cluster Service $29.69) and $17.44 for 2026-10-22T22:00Z to 2026-10-24T22:00Z, where the series of all three label sets are. A range query over 25 days gave no error.
- PromQL refuses a `label_replace` whose output has two series with one label set: the first draft, which set `operation="chat"` on each series, failed with "vector cannot contain metrics with the same labelset" over the range with all three label sets.
- Grafana 13.2.4 (`/api/health`) is the live version. Its documentation says that a constant variable holds "complex values that you need to include in queries", and that the raw format "doesn't apply any data source-specific formatting to the variable".
- genai-prices 0.1.9 gives $2.50 and $10 for each million tokens of `gpt-4o`, and $0.02 and $0 for `text-embedding-3-small`, under the provider `openai`.
- On the base commit, four new tests failed: the default was `gpt-4o-mini` and the rule held the prices, the savings queries read the rule and only `local="true"`, and the panel query was not the recorded query.

## Existing Tool Considered

Prometheus evaluates the savings, and a Grafana constant variable holds the prices. genai-prices stays the source of every price. The test replays the answers of the real Prometheus engine over recorded series, as `tests/support/openspec_recording.py` replays the real OpenSpec. `promtool test rules` is the tool to test a PromQL expression, but no test, CI job or `tools.lock` entry uses promtool, and a stock GitHub runner does not have it. Nothing is built. The change deletes the recording rule group `devops-cli-ai-reference-prices`, the test helper `_reference_price_rules` and the constants `REFERENCE_PRICE_RULE`, `LOCAL_TOKENS`, `PRICED_BY_THE_RULE` and `PRICE_PER_MILLION`.
