# Design

## Decisions

- **The unit is the new tokens of a reply.** `new_tokens(usage) = input_tokens - cache_read_tokens + output_tokens`. These are the tokens that the provider bills at the full input or output price. A cache write is input that the cache did not serve, so it counts. The function takes any object with the three counts (`TokenCounts`): a pydantic-ai `RequestUsage`, a `StepOutcome` and the recorded spend of the earlier Jobs.
- **The step and the item count in the same unit.** `limit_hooks` adds the new tokens of each reply to the step. `JobRun._item_spend` adds the new tokens of the outcomes of this Job and of the record `implement.spend`. The ceiling is in the same unit as the step budget.
- **The record keeps the measured counts, not the unit.** The outcome, the tier spend and the record hold `cache_read_tokens` next to `input_tokens` and `output_tokens`, and the budget computes the unit from them. A record that an older version wrote has no `cache_read_tokens`, so its spend counts in full, by the rule of #4070 that a missing key takes its empty value. This is the larger count, so a continuation never gets more budget than it had.
- **The defaults come from the measured rate.** From 2026-11-05 to 2026-11-11 a request of a runner Job gave 950 to 1570 uncached input tokens and about 360 output tokens. The first request of a step, about 140000 tokens, is not in the cache. 1000000 new tokens is about 500 requests: about the requests of the 90 minutes of `step_time_limit_seconds` at about 10 seconds each. The item budget keeps the ratio 2.5 of the old defaults (2500000), and the ceiling stays twice the default budget (2000000).
- **The test model reports cache reads.** `ModelScript(cached=n)` gives each streamed reply n more input tokens, all of them cache reads, so a test runs a real step on a reply that the cache served. The `FunctionModel` of pydantic-ai estimates the usage of a stream and takes no usage from the script.

## Rejected alternatives

- **A budget in USD.** The project prices the gateway group itself (#4454): genai-prices 0.1.13 does not know `deepseek-v4.1-flash-1017`, so `UsageLimits.cost_limit` and `SpendLimits` cannot price it alone. A local tier costs USD 0, and a model with no price gives USD 0 with a warning, so the budget never stops such a step. The day and item budgets in USD are #3066.
- **The uncached input tokens only.** The output tokens cost 3 times the input price (0.2352 against 0.0784 USD for each million tokens), and a count without them does not bound the output.
- **The number of requests.** It does not change with the size of the context or with the cached share. A provider that caches nothing costs 30 times more for each request.
- **The raw input tokens, as before.** 98.6% of them were cache reads at 3% of the input price, so the budget stopped steps that made progress after USD 0.034 to 0.052.
- **The cached reads at their price ratio (a weighted sum).** It needs the price of each tier at the time of the count, as a USD budget does. The time limits bound the number of requests, and so the cache reads.
