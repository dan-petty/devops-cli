# Proposal: #4387

## Why

The token budgets of `roadmap.implement` add the `input_tokens` of each reply (#4387). Each request sends the whole conversation again, and pydantic-ai counts the prefix that the provider read from its cache in `input_tokens`. In the 48 hours to 2026-11-10T23:45Z, 98.6% of the input tokens of the runner Jobs were cache reads, at 3% of the input price. So the budget of a step was a cap of about 60 to 120 requests, not a cap on cost: 4 of 8 runner Jobs stopped with the class `limit_reached` after USD 0.034 to 0.052 each, and 2 items stay Blocked behind the stops.

The item asked for a report with no production code, and one fix issue for each recommendation. This change replaces those criteria with the fix: the measured data makes the recommendation clear, and a separate fix issue would hold the same change. The comment of 2026-11-11 on the item answers point 2 for the implement step and point 3 with measured data, #4454 answers point 4 (the price of the model with its cached input), and this change answers point 1 (Feasibility). The two points of the stage planner stay open: the cache share of a stage plan run (point 2) and the order of its prompt (point 5). #4583 holds them, so this change closes the item.

## What Changes

- The step budget, its ceiling and the item budget count the new tokens of each reply: the input tokens that the provider did not read from its cache, and the output tokens (`new_tokens` in `implement_limits.py`). A provider that caches nothing reports no cache reads, so each of its input tokens counts.
- The defaults keep their values: `step_token_budget` 8000000 and `item_token_budget` 20000000. The ceiling stays twice the budget (#4505). A route that reports no cache reads, such as the local `devops-coder` group of the default ladder, counts each input token, so its steps keep their room. On the cached hosted route, the time limit of the step stops it first.
- The outcome of a step, the spend of each tier and the record `implement.spend` keep `cache_read_tokens`. The record keeps the count of the item budget as `new_tokens`, and the item budget counts the `new_tokens` of the earlier Jobs of the item. A record that an older version wrote has no `new_tokens`, so its Jobs count none: its input tokens hold cache reads in an unknown share.
- The reasons of a stop at the token budget, the Job log line and the comment line of an extension say "new tokens".
- `ModelScript` of the tests takes `cached` input tokens for each streamed reply.
- The descriptions of the three settings, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md` and the generated `docs/ENV_VARS.md` state the unit.

The stop of a step and its settings are behavior that a consumer observes, so the change has a delta for `roadmap-implement-step`.

## Capabilities

- `roadmap-implement-step` (modified): one ADDED requirement (a token budget counts the new tokens of a reply, and the record keeps its count as `new_tokens`) and four MODIFIED requirements (the unit of the budgets, and the text of the stop and the extension). The requirement of the ceiling states its unit as the unit of `step_token_budget` (#4505), so it needs no change.

## Impact

- The live ConfigMap sets `roadmap.implement.step_token_budget: 12000000`. The ceiling follows the budget (#4505), so the settings load with that value. On the cached hosted route of the live ladder, 12000000 new tokens are about 6200 requests, so the time limit of the step stops a step first. The line can stay until the new image runs, and then go.
- A step on the cached hosted route can make about 4100 requests before its token budget, so the 90 minutes of its time limit (about 540 requests) stop it first. A step on a route that reports no cache reads makes about 200 requests of 39300 tokens, as before.
- The record `implement.spend` has two more keys, `cache_read_tokens` in its totals and in each tier, and `new_tokens` in its totals. After the rollout, an item whose earlier Job wrote the record with the old image counts none of those tokens for its item budget.
- The change fits one pull request.

## Feasibility

- pydantic-ai 2.59.0, `pydantic_ai/usage.py`, `UsageBase.input_tokens`: "this total includes cached tokens (`cache_read_tokens`, `cache_write_tokens`)". `OpenAIChatModel` maps `prompt_tokens_details.cached_tokens` of the reply to `cache_read_tokens` through the genai-prices extractors (`pydantic_ai/models/openai.py`, `_map_usage`).
- The gateway keeps the field for the CLI: on 2026-11-11, `devops_cli_ai_spend_usd_total` of the Service row `refine` over 3 hours was USD 0.05228 for 1369114 prompt and 117587 completion tokens. At the rates of #4454 (0.0784, 0.002352 and 0.2352 USD for each million tokens), that cost needs about 1090000 cached prompt tokens (79%), which the CLI reads from `cache_read_tokens` of the replies (`record_run_spend`). With no cached tokens, the cost would be USD 0.135.
- Gateway metrics for `end_user="devops-cli-job"` (`litellm_input_tokens_metric_total`, `litellm_provider_cache_read_input_tokens_metric_total`, `litellm_output_tokens_metric_total`, `litellm_proxy_total_requests_metric_total`): from 2026-11-05 to 2026-11-11, each day gave 950 to 1570 uncached input tokens for each request, and the 7 days gave 2952952 output tokens in 8228 requests (about 360 for each request). The 4 stops of 2026-11-10 had 91000 to 154000 new tokens.
- The same metrics by `model` for the 14 days to 2026-11-11 (`litellm_requests_metric_total`): the cached hosted route gave 83669 input tokens, 1486 of them not from the cache, and 442 output tokens for each of 4911 requests. The local route `qwen3-coder:30b`, which the runner Jobs used until 2026-11-05, gave 39274 input tokens and 201 output tokens for each of 14642 requests, and no series of cache reads. Only the hosted DeepSeek route has a series of cache reads: the local routes and `claude-sonnet-5-5` report none.
- The code: `limit_hooks` adds `response.usage.input_tokens` (`implement_limits.py`), and `JobRun._item_spend` adds the `input_tokens` of the outcomes and of the record.

## Existing Tool Considered

- pydantic-ai `UsageLimits` (2.59.0): `input_tokens_limit` and `total_tokens_limit` include cache reads, as its own documentation says. `cost_limit` prices each reply with genai-prices, and genai-prices 0.1.13 has no price for `deepseek-v4.1-flash-1017`.
- pydantic-ai-harness `SpendLimits` (0.59.0, a project dependency): `Budget(tokens=...)` counts `total_tokens`, with the cache reads. `Budget(usd=...)` needs a `price=` function, has no rule for the one extension of a step (#4394), and keeps its count in a store and not in the record of the item across Jobs. A local tier costs USD 0, so a USD budget never stops a step on it.
- The change builds instead: one function of one line, one field in four models, and new defaults. Cost: about 200000 tokens to build, about 2 hours elapsed, and small to keep, because the unit comes from three fields of pydantic-ai usage. A USD budget for the items and the days is #3066.
- The change deletes no internal code: the count changes where it is.
