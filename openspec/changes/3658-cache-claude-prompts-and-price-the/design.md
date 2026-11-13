# Design

## Decisions

### Two injection points on each Claude group

Each Claude group sets these points in `litellm_params`, in this order:

```yaml
cache_control_injection_points:
  - location: message
    role: system
  - location: message
    index: -1
```

Anthropic renders a request in the order tools, system, messages. A breakpoint caches the full prefix up to its block. So:

- The system point caches the tool definitions and the system prompt. Calls that share them (a review round, the next run of the same stage, an eval case) read this prefix from the cache, also when their messages differ.
- The last-message point caches the full history of an agent run. The next request of the run sends the same history plus one tool call and one tool result, so it reads all of the earlier history from the cache and writes only the new part. This is the large saving: a stage attempt sends about 10 million prompt tokens over its requests, and most of them are history that the run sent before.

LiteLLM puts the system marker on each system message. pydantic-ai sends each system prompt part and each instructions part as one system message, so a request with one or two system messages uses two or three breakpoints. LiteLLM stops at the Anthropic limit of 4 (`MAX_CACHE_CONTROL_BLOCKS`) and applies the points in config order. A request with four or more system messages thus keeps its system markers and loses the last-message marker: it caches less, but it does not fail. The number of system messages of each agent is not counted in this change. The cache hit share that the release measures shows such a loss.

The agents send `parallel_tool_calls` false (#4228), so each request of a run adds one tool call and one tool result: two positions. The lookback of Anthropic is 20 positions, so the breakpoint of the next request always finds the entry of the request before it.

### The 5-minute TTL

The points send no `ttl`, so the marker is `{type: ephemeral}` with the 5-minute TTL. A cache write costs 1.25 times the input price with the 5-minute TTL and 2 times with the 1-hour TTL. A read refreshes the timer. The requests of an agent run start less than 5 minutes apart, so the 5-minute TTL keeps the cache warm for the full run at the lower write price.

### The ledger stores both counts and genai-prices prices them

`track_request_spend` takes `cache_read_tokens` (#4403) and now `cache_write_tokens`. Both are parts of `prompt_tokens`, as in the OpenAI usage, in pydantic-ai and in genai-prices. `_genai_prices_cost` gives both to `genai_prices.Usage`, and genai-prices applies the cache rates of the model. The ledger row stores both counts, so a report can give the cache hit share without a new metric.

A price override (`ai.price_overrides`, the file of `set-price`) and `_HOSTED_GROUP_PRICES` have a cached input rate but no cache write rate. Such a price costs a cache write token at the prompt rate, which is the behavior before this change. Only genai-prices prices the Claude groups, so this gap has no effect on them.

### Where the counts come from

| Path | Source of the cache write count |
| --- | --- |
| Spend hook of `build_agent` | `ModelResponse.usage.cache_write_tokens`. pydantic-ai fills it from `prompt_tokens_details.cache_write_tokens` of the gateway reply. |
| `record_run_spend` | The sum of `cache_write_tokens` of the replies of the run. |
| Blocking chat call of `LLMClient` | `usage.prompt_tokens_details.cache_write_tokens` of the reply. |
| Streamed chat call of `LLMClient` | The same field of the final usage frame. |

A failed attempt (`record_failed_attempt`) keeps its cache read count only. An error reply of the gateway carries no cache write, because Anthropic writes a cache only for a request that it runs.

The direct Anthropic client (`devops_cli/ai/client/claude.py`) sends no cache marker, so its replies have no cache tokens. This change does not touch it.

### The gateway test holds the points

`_hosted_violations` gets three rules:

- A group whose model starts with `anthropic/` sets the system point and the last-message point.
- It sets at most 4 points, the Anthropic limit.
- No other group sets `cache_control_injection_points`.

## Rejected alternatives

- **The global flag `litellm_settings.enable_anthropic_prompt_caching: true`.** LiteLLM 1.103.11 then adds the same two points to each Claude deployment. But the flag is not on the group, the hosted-group test cannot tell which group it covers, and it applies to every Claude deployment that a later change adds, with no review of that group. The group setting is explicit and the test holds it.
- **The system point only.** It caches the tools and the system prompt but not the history. In an agent run the history is the largest part of the prompt, so most of the saving is lost.
- **The last-message point only.** It caches the full prefix of a run, but a new run with the same tools and system prompt and other messages misses: no entry ends at the system prompt.
- **A `tool_config` point.** LiteLLM uses that location for Bedrock Converse. The tools render before the system prompt, so the system point caches them already.
- **The 1-hour TTL.** It doubles the write price. The requests of a run start less than 5 minutes apart, so the 5-minute entry stays warm.
- **A top-level `cache_control` (Anthropic automatic caching) in the `extra_body` of the group.** Every call with the group would carry it, but the automatic breakpoint moves to the last block only. It gives no fixed read point at the system prompt, and the pinned LiteLLM documents the injection points as its control for this.
- **A `cache_control` marker from each caller of devops-cli.** Each stage, review and eval call would repeat the logic, and a new caller that forgets it loses the cache. The gateway is the one control point for every caller.
- **The LiteLLM `response_cost` as the ledger cost.** It covers a gateway call only. The ledger also prices agent runs and local calls, and a release of the CLI must not depend on a reply field of the gateway.
- **A new token type `cache_read` or `cache_write` on `devops_cli_ai_tokens_total`.** The AI spend dashboard and the snapshot of `devops ui` sum that series over its types, so new types would count the cache tokens twice. The gateway exports `litellm_input_cached_tokens_metric_total` and `litellm_input_cache_creation_tokens_metric_total` for each model already, and the ledger rows hold the counts.
