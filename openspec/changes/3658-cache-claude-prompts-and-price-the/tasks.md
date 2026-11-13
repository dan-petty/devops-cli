# Tasks

## 1. Gateway cache points (behavior)

- [x] 1.1 Write failing tests: `_hosted_violations` reports a Claude group with no system point, a Claude group with no last-message point, a Claude group with more than 4 points, and another group with a point
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py`
- [x] 1.2 Set the system point and the last-message point on `claude-sonnet-5-5` and `claude-haiku-5-5` in `k8s/llm/gateway/config.yaml`, and add the three rules to `_hosted_violations`
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py`

## 2. Ledger cache tokens (behavior)

- [x] 2.1 Write failing tests: the ledger stores the cache read and cache write tokens of a row, an old ledger gains both columns and keeps its rows, a Sonnet call of 2,000,000 prompt tokens with 1,000,000 cache reads and 1,000,000 cache writes costs 2.60 USD, and the client price of each hosted group equals the gateway price at the cache write rate
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_ledger_cache_tokens.py tests/ai/spend/test_hosted_group_prices.py`
- [x] 2.2 Add the columns `cache_read_tokens` and `cache_write_tokens` to the ledger and to `SpendRecord`, and add `cache_write_tokens` to `track_request_spend`, `calculate_request_cost` and `_genai_prices_cost`
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_ledger_cache_tokens.py tests/ai/spend/test_hosted_group_prices.py`

## 3. Callers give the cache write tokens (behavior)

- [x] 3.1 Write failing tests: the spend hook of `build_agent` and `record_run_spend` record the cache write tokens of the replies, and a blocking and a streamed chat call of `LLMClient` record the cache write tokens of the gateway usage
  - Verification: `$ uv run devops ci test tests/ai/client/test_agent_factory.py tests/ai/client/test_roadmap_agent_run.py tests/ai/spend/test_ai_spend_dispatch.py`
- [x] 3.2 Pass `cache_write_tokens` from the spend hook, `record_run_spend`, `LLMResponse`, `StreamUsage` and the two recorders of `UnifiedLLMClient`
  - Verification: `$ uv run devops ci test tests/ai/client/test_agent_factory.py tests/ai/client/test_roadmap_agent_run.py tests/ai/spend/test_ai_spend_dispatch.py`

## 4. Documents

- [x] 4.1 Tell in `k8s/README.md` how the Claude groups cache their prefix and how the ledger prices the cache tokens
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
- After the release, measure the cache hit share of the live Sonnet calls (`litellm_input_cached_tokens_metric_total` over `litellm_input_tokens_metric_total` for `claude-sonnet-5-5`) and post it on #3658.
