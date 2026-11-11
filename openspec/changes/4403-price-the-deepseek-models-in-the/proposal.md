# Proposal: #4403

## Why

The group `deepseek-v4.1-flash-1017` runs every chat slot of the Service, but nothing prices it. genai-prices 0.1.13 does not know the model, and no `ai.price_overrides` entry names it, so each call records 0 USD with the source `unknown` (#4403). `devops_cli_ai_spend_usd_total` held 0 USD for the group over the 3 days to 2026-11-11, while the gateway recorded 15.09 USD for the same calls. `devops ai cost` and the alert `HostedSpendDailyHigh` cannot see the spend of the Service.

A price alone does not give the real cost. The client prices every prompt token at the prompt price, and 94% of the prompt tokens of the group come from the cache of the provider, at about 3% of the prompt price. At the gateway rates of 2026-11-02 with no cached input rate, the client would record 71 USD for those 3 days, which is about 24 USD a day: just below the 25 USD threshold of `HostedSpendDailyHigh`, for a real cost of about 5 USD a day.

## What Changes

- Add `_HOSTED_GROUP_PRICES` to `src/devops_cli/ai/spend/pricing.py`: the price of each hosted gateway group that genai-prices does not price, under the route name and under the deployment model of the group. It holds DeepSeek V4.1 Flash 1017 at 0.0784 USD input, 0.0024 USD cached input and 0.2352 USD output per million tokens. The file of `set-price` wins over `ai.price_overrides`, and both win over this table. The price needs no ConfigMap entry and no hand step, so the workstation and the Service record it as soon as they run the new code.
- Add a cached input rate: `ModelPricing.cache_read_usd_per_million` and `AIPriceOverride.cache_read_usd_per_million`, both optional. With no rate, a cached prompt token costs the prompt price, as before.
- `calculate_request_cost` and `track_request_spend` take `cache_read_tokens`, the part of the prompt tokens that the provider read from its cache. The price of a table or a setting uses its cached input rate. A genai-prices price gets the tokens in `genai_prices.Usage(cache_read_tokens=...)`, so a Claude group costs its own cache-read rate too.
- `record_run_spend` gives the sum of `RequestUsage.cache_read_tokens` of the replies of a run. A run of an agent is 99% of the DeepSeek tokens in the workstation ledger (2,469 rows and 174 M prompt tokens against 14 chat rows).
- Set the same three rates in the `model_info` of the group in `k8s/llm/gateway/config.yaml`, with the source and the date.
- Add `tests/ai/spend/test_hosted_group_prices.py`: it fails when a hosted group of the gateway config has no price under its route name or its deployment model, when a model that the Service template names is not a gateway group that is priced or local, or when the client price of a hosted group differs from the price in the gateway config.
- Change the tests and spec scenarios that used DeepSeek as the example of an unpriced model to an example model that nothing prices.
- The service behavior changes (a spend metric and a manifest), so the change carries a delta of `ai-spend-pricing`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: every hosted gateway group has a price, cached prompt tokens cost the cached input rate, and the client price of a group is the price in the gateway config

## Impact

- Code: `src/devops_cli/ai/spend/pricing.py`, `src/devops_cli/ai/spend/models.py`, `src/devops_cli/ai/spend/ledger.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/telemetry/instruments.py`
- Manifest: `k8s/llm/gateway/config.yaml` (prices only; Argo CD applies it)
- Documents: `k8s/README.md`, `docs/TELEMETRY.md`
- Tests: `tests/ai/spend/test_hosted_group_prices.py` (new), `tests/ai/client/test_roadmap_agent_run.py`, `tests/ai/spend/test_ai_spend_pricing.py`
- The live ConfigMap `devops-cli-config` needs no change. #4423, which applies a price to it by hand, has no work left after this change.
- The alert thresholds stay: `ClaudeSpendDailyHigh` at 15 USD and `HostedSpendDailyHigh` at 25 USD. At the new price the Service records about 5 USD a day of DeepSeek spend.

## Feasibility

- genai-prices: `uv run python` with genai-prices 0.1.13 raises `LookupError` for `deepseek-v4.1-flash-1017`, `deepseek/deepseek-v4.1-flash-1017` and `openrouter/deepseek/deepseek-v4.1-flash-1017:floor` under the providers none, `litellm` and `openrouter`. It prices `claude-sonnet-5-5` (2 and 10 USD), `claude-haiku-5-5` (0.10 and 0.50 USD below 100,000 tokens) and `gemini-3.8-flash` (0.75 and 3.75 USD). The wheel of genai-prices 0.2.3 (PyPI, 2026-11-10) knows `deepseek/deepseek-v4.1-flash-1017` at 0.30 USD input, 0.006 USD cached input and 1.20 USD output: the list price of DeepSeek, not the price of the route `:floor` with fp8 weights.
- Cause: the local ledger rows of the group after #3665 have the source `unknown`, not `local` (2,469 `agent_run` rows that name the route name, and 14 `chat_dispatch` rows that name `openrouter/deepseek/deepseek-v4.1-flash-1017:floor`). So the missing price is the cause, and a price under only one of the two names misses the other rows.
- Price: the OpenRouter API `https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash-1017/endpoints`, read with no key on 2026-11-11 at 00:37 UTC, lists 21 fp8 endpoints. It gives no data policy, so it cannot show which endpoint passes `data_collection: deny`. The cost that the gateway recorded (`litellm_spend_metric_total`) for each of its three callers from 2026-11-08 to 2026-11-11 differs from its own rates of 2026-11-02 (0.05, 0.008 and 0.192 USD) by 20% to 117%, so the gateway records the cost that OpenRouter reports. At the rates of the endpoint `deepinfra/fp8/flex` (0.0784, 0.0024 and 0.2352 USD), the three callers cost 12.95, 1.89 and 0.56 USD against the recorded 12.69, 1.87 and 0.53 USD (within 7%). A solve of the three callers gives 0.0747, 0.0021 and 0.2503 USD.
- Cached tokens: the gateway counted 1,248.7 M cached of 1,332.4 M prompt tokens for the group in the same 3 days (`litellm_input_cached_tokens_metric_total`). A probe of three pydantic-ai runs through the gateway on 2026-11-11, with a prompt of 4,437 tokens, read `cache_read_tokens` 0, 4,352 and 4,352, and the reply names the route name. pydantic-ai 2.59.0 takes `prompt_tokens_details.cached_tokens` through the genai-prices extractor, and `genai_prices.Usage` counts `cache_read_tokens` inside `input_tokens`, as pydantic-ai does.

## Existing Tool Considered

genai-prices is the open, maintained price library that the project uses, and it prices the Gemini and Claude groups. Its 0.1.13 data has no price for the DeepSeek snapshot. Its 0.2.3 data has the list price, which is about 4 to 5 times the price of the route, and it is less than two weeks old. `ai.price_overrides` (#4242) holds a price that genai-prices does not know, but it needs a person to apply the live ConfigMap and it does not reach the workstation. The change builds one table of two keys and one cached input rate on the existing override path, and deletes no code. The cost is about 120,000 tokens to build and review, and 10 minutes of CI. Keeping it costs one edit of the table and the gateway config when the route price moves; the test makes the two edits go together.
