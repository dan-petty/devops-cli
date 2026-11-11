# Tasks

## 1. Behavior

- [x] 1.1 Write `test_a_chat_call_on_the_deepseek_group_costs_its_cached_and_new_input_and_its_output` for a chat call, a stream and a failed attempt, with the ledger amount 0.033477 USD
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_dispatch.py`
- [x] 1.2 Add `cache_read_tokens` to `LLMResponse` and `StreamUsage`, read it in the OpenAI-compatible provider and the failed-attempt recorder, and give it to `track_request_spend` in the `chat_dispatch` and `stream` recorders
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_dispatch.py tests/ai/client/test_agent_factory.py`
