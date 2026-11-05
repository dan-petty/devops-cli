# Proposal

## Why

Issue #3656: a call to a hosted gateway group (`claude-sonnet-5-5`, `claude-haiku-5-5`, `deepseek-v4.1-flash-1017`) is recorded as a local call at $0, and its tokens count as local savings. The ledger of the owner holds 354 such rows. The hosted groups set no `api_base`, so the gateway reply names no backend, and `is_local` then decides from the server that the call was sent to. That server is the gateway, a local host. The reply does name the deployment model (`x-litellm-model-name`), and `is_local` does not read it.

A second gap: genai-prices holds no price for `deepseek-v4.1-flash-1017`. The warning for it does not say how to set a price.

## Feasibility

- The local ledger (`.data/ai/spend.db`, 2026-11-05) groups the rows with a deployment model that starts with `anthropic/` or `openrouter/`: 354 rows, `served_by` NULL in all, `pricing_source` `local` in all. Every row with a `served_by` is a cluster backend. The query is in issue #3656.
- `genai_prices.calc_price` (genai-prices 0.1.13) prices `claude-sonnet-5-5` and `claude-haiku-5-5` at the provider `anthropic` (2.0 and 10.0 USD per million tokens for Sonnet, the prices of the gateway group), and `gemini-3.8-flash` at the provider `google`. It raises `LookupError` for `deepseek-v4.1-flash-1017` under the providers `litellm` and `openrouter`.
- The upstream data (`https://raw.githubusercontent.com/pydantic/genai-prices/refs/heads/main/prices/new_data/v2/data.json`, 2026-11-05) lists `deepseek/deepseek-v4.1-flash` under `openrouter` and no `-1017` snapshot. Its price (0.0352 to 0.0448 USD input, 0.08 USD output per million) is not the price of the group (0.05 and 0.192 in `k8s/llm/gateway/config.yaml`), so a lookup by the base name would price the group wrongly.
- `devops ai gateway render` and `tests/ai/benchmark/test_k8s_llm_gateway.py` already treat a deployment with no `api_base` as hosted.

## Existing Tool Considered

genai-prices prices the Claude and Gemini groups once the ledger asks it. For the DeepSeek group the open mechanism is the price override that the repository already has (`devops ai cost set-price`), keyed by the deployment model. The change builds no price table and no model-name matching. It makes the warning name the command. It deletes no code.

## What Changes

- `is_local` takes `served_model`. A reply of the `gateway` provider that names a deployment model and no backend is hosted. `calculate_request_cost` passes the deployment model, and the lifetime report groups the served usage by it, so a hosted group no longer counts in local savings or sets `local` on its tokens.
- The warning for an unpriced hosted model adds the command `devops ai cost set-price <model> <prompt_rate> <completion_rate>`.
- `tests/ai/benchmark/test_k8s_llm_gateway.py` fails when an in-cluster deployment sets no `api_base`: the ledger would count its calls as hosted.
- The spec delta adds two requirements to `ai-spend-pricing`.
- The change fits one pull request.

## Impact

- Rows that the ledger recorded before this change keep the source `local`. No migration: a row records what the process knew when it wrote it.
- The DeepSeek group has the source `unknown` and a $0 cost until a person sets a price with the command that the warning names. The three known prices differ (the gateway config, the OpenRouter list, genai-prices), so the change chooses none.
