# Proposal: #3658

## Why

The gateway groups `claude-sonnet-5-5` and `claude-haiku-5-5` send the same prefix on each call: the tool definitions, the system prompt and, in an agent run, the history of the run. Nothing asks Anthropic to cache that prefix, so each request pays the full input price for each prompt token (#3658). Sonnet 5.5 now runs live on the verification slot (stage plan review, `refine_judge` and the fix-plan review). In the 24 hours to 2026-11-13 23:30 UTC the gateway counted about 0.82 million Sonnet input tokens and no cached token (`litellm_input_cached_tokens_metric_total` has no Claude series). A stage attempt is an agent loop that sends its growing history again on each request, so a cache of the conversation prefix gives the largest saving.

The spend ledger also gives the wrong cost for a cached Claude call. It stores no cache read count and no cache write count. A cache write is part of the prompt tokens, so the ledger prices it at the input price (2.00 USD per million on Sonnet 5.5), but Anthropic bills it at the cache write price (2.50 USD per million, 1.25 times the input price). The ledger prices cache reads at the cache read rate already (#4403), but it does not keep the count, so a report cannot show the cache hit share.

## What Changes

- Each Claude group in `k8s/llm/gateway/config.yaml` sets `cache_control_injection_points` with two points: the system messages (`location: message`, `role: system`) and the last message (`location: message`, `index: -1`). LiteLLM writes the Anthropic marker `cache_control: {type: ephemeral}` on these blocks. The system point caches the tool definitions and the system prompt, which many calls share. The last-message point caches the full history of an agent run, so the next request of the run reads it from the cache. The groups of DeepSeek, Gemini and OpenRouter do not change.
- The gateway test `_hosted_violations` reports a Claude group that loses one of the two points or sets more than four points, and any other group that sets an injection point.
- `calculate_request_cost` and `track_request_spend` take `cache_write_tokens`, the part of the prompt tokens that the provider wrote to its cache. genai-prices gets it in `Usage(cache_write_tokens=...)` and prices it at the cache write rate of the model. A price override or a built-in group price has no cache write rate, so a cache write token costs the prompt rate there, as before.
- The spend ledger table `ai_spend_records` gets two columns, `cache_read_tokens` and `cache_write_tokens`. A ledger that exists already gets them in place through `_ADDED_COLUMNS` and keeps its rows. `SpendRecord` holds the two counts.
- The callers give the cache write count: the spend hook of `build_agent` (`RequestUsage.cache_write_tokens`), `record_run_spend` (the sum over the replies of a run), and a chat call of `LLMClient`, blocking or streamed (`usage.prompt_tokens_details.cache_write_tokens` of the gateway reply).
- `tests/ai/spend/test_hosted_group_prices.py` compares the client cost with the gateway cost at the cache write price too, for each hosted group that sets its prices.
- `k8s/README.md` tells how the Claude groups cache and how the ledger prices the cache tokens.
- The behavior of a manifest and of the spend ledger changes, so the change carries deltas of `ai-gateway-routing` and `ai-spend-pricing`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: a Claude group sets two cache injection points, and no other group sets one.
- `ai-spend-pricing`: each ledger row keeps its cache read and cache write tokens, a cache write token costs the cache write rate, and the client price of a hosted group equals the gateway price at the cache write rate too.

## Impact

- Manifest: `k8s/llm/gateway/config.yaml`, the two Claude groups only. Argo CD applies it when the pull request merges. The ConfigMap hash in the kustomization changes, so the gateway Deployment restarts once.
- Code: `src/devops_cli/ai/spend/ledger.py`, `src/devops_cli/ai/spend/models.py`, `src/devops_cli/ai/spend/pricing.py`, `src/devops_cli/ai/client/factory.py`, `src/devops_cli/ai/client/openai.py`, `src/devops_cli/ai/client/models.py`, `src/devops_cli/ai/client/network.py`, `src/devops_cli/ai/client/unified.py`, `src/devops_cli/roadmap/agent_run.py`. The ledger change takes effect with the next release.
- Tests: `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/ai/spend/test_hosted_group_prices.py`, `tests/ai/spend/test_ai_spend_ledger_cache_tokens.py` (new), `tests/ai/spend/test_ai_spend_dispatch.py`, `tests/ai/client/test_agent_factory.py`, `tests/ai/client/test_roadmap_agent_run.py`.
- Documents: `k8s/README.md`.
- Overlap: the DeepSeek fallback of #5564 edits the same gateway config, gateway test, `k8s/README.md` paragraph area and spec `ai-gateway-routing`. This change is on top of it. It edits only the Claude entries of the config and a requirement that #5564 does not change, and no DeepSeek, Gemini or OpenRouter group.
- Cost: at the Sonnet 5.5 prices, a request that reads a 100,000-token prefix from the cache costs 0.01 USD for that prefix, against 0.20 USD with no cache. The first request of a prefix costs 0.25 USD for it (the write premium of 25%). Two requests within 5 minutes pay back the write.

## Feasibility

The premise was checked against the real system on 2026-11-13:

- Pinned image: `k8s/llm/gateway/deployment.yaml` pins `ghcr.io/berriai/litellm:v1.103.11`. The wheel `litellm-1.103.11` (PyPI) holds `litellm/integrations/anthropic_cache_control_hook.py`. It reads `cache_control_injection_points` from the parameters of a deployment, targets a message by `role` or by `index` (a negative index counts from the end), puts the marker on the last content block of a message, and stops at the Anthropic limit of 4 breakpoints (`MAX_CACHE_CONTROL_BLOCKS`). Its own default points for `litellm.enable_anthropic_prompt_caching` are the same two points as this change.
- Local LiteLLM run: the proxy of `litellm[proxy]==1.103.11` ran with the `claude-sonnet-5-5` entry of the gateway config, the two points, and a loopback stub in place of the Anthropic API that recorded each request body. An agent-loop request (system, user, assistant tool call, tool result, one tool) reached the stub with `cache_control: {type: ephemeral}` on the system block and on the `tool_result` block of the last message, and on no other block. A streamed request with `stream_options.include_usage` got the same markers. For a stub usage of 50 input, 1,200 cache write and 300 cache read tokens, the blocking reply and the final frame of the stream both gave `prompt_tokens` 1,550 and `prompt_tokens_details` with `cached_tokens` 300 and `cache_write_tokens` 1,200, plus `cache_read_input_tokens` and `cache_creation_input_tokens`.
- Live gateway: two calls to `claude-haiku-5-5` through the live gateway, with the same two points sent in the request body, and a system prompt of about 3,300 tokens. The first reply gave `cache_write_tokens` 3,310 and `cached_tokens` 0. The second reply gave `cache_write_tokens` 0 and `cached_tokens` 3,310. So the Anthropic key, the pinned image and the reply format work together. The two calls cost less than 0.001 USD.
- pydantic-ai 2.59.0: `_map_usage` of `OpenAIChatModel` maps the reply above to `RequestUsage` with `input_tokens` 1,550, `cache_read_tokens` 300 and `cache_write_tokens` 1,200 under the provider `openai`, which the bridge uses for the gateway. The spend hook reads `cache_read_tokens` only today.
- genai-prices 0.2.3: `calc_price(Usage(input_tokens=2_000_000, cache_read_tokens=1_000_000, cache_write_tokens=1_000_000), "claude-sonnet-5-5")` gives 2.60 USD (0.10 USD for the reads and 2.50 USD for the writes), with and without the providers `anthropic` and `litellm`. `claude-haiku-5-5` gets its own cache rates, also the tier above 100,000 tokens.
- Prices: the Claude groups already set `cache_creation_input_token_cost` and `cache_read_input_token_cost` in `model_info` (2.5e-06 and 1.0e-07 for Sonnet, 1.25e-07 and 1.0e-08 for Haiku), equal to the genai-prices rates. `_HOSTED_GROUP_PRICES` holds DeepSeek only, so genai-prices prices the Claude groups.
- Minimum prefix: Anthropic caches a prefix of 512 tokens or more on Sonnet 5.5 and Haiku 5.5. The system prompts of the review and stage agents are longer than that.

## Existing Tool Considered

LiteLLM (BerriAI/litellm, the pinned gateway image) puts the cache markers on the request through `cache_control_injection_points`, and genai-prices (pinned 0.2.3) prices cache reads and cache writes. The change uses both and builds no cache logic. The global flag `litellm.enable_anthropic_prompt_caching` sets the same two points for every Claude deployment, but a flag in `litellm_settings` is not visible on the group and no test of the group can hold it; the design records why the change uses the group setting. No tool writes the cache counts into the project's spend ledger, so the change adds two columns and passes one more count through the existing callers: about 90 lines of code and 250 lines of tests, about 150,000 tokens to build and review, and about 15 minutes of CI. The change deletes no code.
