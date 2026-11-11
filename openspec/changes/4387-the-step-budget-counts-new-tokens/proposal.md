# Proposal: #4387

## Why

The token budgets of `roadmap.implement` add the `input_tokens` of each reply (#4387). Each request sends the whole conversation again, and pydantic-ai counts the prefix that the provider read from its cache in `input_tokens`. In the 48 hours to 2026-11-10T23:45Z, 98.6% of the input tokens of the runner Jobs were cache reads, at 3% of the input price. So the budget of a step was a cap of about 60 to 120 requests, not a cap on cost: 4 of 8 runner Jobs stopped with the class `limit_reached` after USD 0.034 to 0.052 each, and 2 items stay Blocked behind the stops.

The item asked for a report and one fix issue for each recommendation. The comment of 2026-11-11 on the item answers its points 2 and 3 with measured data, and #4454 answers point 4 (the price of the model with its cached input). This change is the fix of the recommendation, so it closes the item and files no separate fix issue.

## What Changes

- The step budget, its ceiling and the item budget count the new tokens of each reply: the input tokens that the provider did not read from its cache, and the output tokens (`new_tokens` in `implement_limits.py`). A provider that caches nothing reports no cache reads, so each of its input tokens counts.
- The defaults change with the unit: `step_token_budget` 1000000, `step_token_ceiling` 2000000 (twice the default budget) and `item_token_budget` 2500000.
- The outcome of a step, the spend of each tier and the record `implement.spend` keep `cache_read_tokens`. The item budget counts the new tokens of the earlier Jobs of the item. A record that an older version wrote has no `cache_read_tokens`, so each of its input tokens counts.
- The reasons of a stop at the token budget, the Job log line and the comment line of an extension say "new tokens".
- `ModelScript` of the tests takes `cached` input tokens for each streamed reply.
- The descriptions of the three settings, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md` and the generated `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` state the unit.

The stop of a step and its settings are behavior that a consumer observes, so the change has a delta for `roadmap-implement-step`.

## Capabilities

- `roadmap-implement-step` (modified): one ADDED requirement (a token budget counts the new tokens of a reply) and five MODIFIED requirements (the unit and the defaults of the budgets and the ceiling, and the text of the stop and the extension).

## Impact

- The live ConfigMap sets `roadmap.implement.step_token_budget: 12000000`. With this change, that value is above the default ceiling of 2000000, so the settings do not load until #4505 makes the ceiling follow the budget. In the new unit, 12000000 is also 12 times the default. Delete the line from the live ConfigMap before the image with this change rolls out. The image that runs now then uses its own default of 8000000 input tokens, and the new image uses 1000000 new tokens.
- A step on the cached gateway route can make about 500 requests before its token budget, about the requests of its 90 minutes. A step on a provider that caches nothing stops after about 8 requests of 130000 tokens, at about USD 0.08.
- The record `implement.spend` has one more key, `cache_read_tokens`, in its totals and in each tier.
- The change fits one pull request.

## Feasibility

- pydantic-ai 2.59.0, `pydantic_ai/usage.py`, `UsageBase.input_tokens`: "this total includes cached tokens (`cache_read_tokens`, `cache_write_tokens`)". `OpenAIChatModel` maps `prompt_tokens_details.cached_tokens` of the reply to `cache_read_tokens` through the genai-prices extractors (`pydantic_ai/models/openai.py`, `_map_usage`).
- The gateway keeps the field for the CLI: on 2026-11-11, `devops_cli_ai_spend_usd_total` of the Service row `refine` over 3 hours was USD 0.05228 for 1369114 prompt and 117587 completion tokens. At the rates of #4454 (0.0784, 0.002352 and 0.2352 USD for each million tokens), that cost needs about 1090000 cached prompt tokens (79%), which the CLI reads from `cache_read_tokens` of the replies (`record_run_spend`). With no cached tokens, the cost would be USD 0.135.
- Gateway metrics for `end_user="devops-cli-job"` (`litellm_input_tokens_metric_total`, `litellm_provider_cache_read_input_tokens_metric_total`, `litellm_output_tokens_metric_total`, `litellm_proxy_total_requests_metric_total`): from 2026-11-05 to 2026-11-11, each day gave 950 to 1570 uncached input tokens for each request, and the 7 days gave 2952952 output tokens in 8228 requests (about 360 for each request). The 4 stops of 2026-11-10 had 91000 to 154000 new tokens.
- The code: `limit_hooks` adds `response.usage.input_tokens` (`implement_limits.py`), and `JobRun._item_spend` adds the `input_tokens` of the outcomes and of the record.

## Existing Tool Considered

- pydantic-ai `UsageLimits` (2.59.0): `input_tokens_limit` and `total_tokens_limit` include cache reads, as its own documentation says. `cost_limit` prices each reply with genai-prices, and genai-prices 0.1.13 has no price for `deepseek-v4.1-flash-1017`.
- pydantic-ai-harness `SpendLimits` (0.59.0, a project dependency): `Budget(tokens=...)` counts `total_tokens`, with the cache reads. `Budget(usd=...)` needs a `price=` function, has no rule for the one extension of a step (#4394), and keeps its count in a store and not in the record of the item across Jobs. A local tier costs USD 0, so a USD budget never stops a step on it.
- The change builds instead: one function of one line, one field in four models, and new defaults. Cost: about 200000 tokens to build, about 2 hours elapsed, and small to keep, because the unit comes from three fields of pydantic-ai usage. A USD budget for the items and the days is #3066.
- The change deletes no internal code: the count changes where it is.
