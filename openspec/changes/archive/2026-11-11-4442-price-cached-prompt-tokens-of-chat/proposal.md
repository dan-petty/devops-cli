# Proposal: #4442

## Why
A chat call of `LLMClient` records all its prompt tokens at the full prompt price. The reply names the prompt tokens that the provider read from its cache (`usage.prompt_tokens_details.cached_tokens`), but the client does not read them. Since #4403 the pricing registry prices cached prompt tokens at the cached input rate, and since #4475 the hook of `build_agent` gives them. The spend recorders of a chat call give 0. Thus a chat call on the DeepSeek group with 900,000 of its 1,000,000 prompt tokens from the cache records 0.10192 USD, not 0.033477 USD. Closes #4442.

## What Changes
- `LLMResponse` and `StreamUsage` get the field `cache_read_tokens`. The OpenAI-compatible provider sets it from `usage.prompt_tokens_details.cached_tokens` of a reply and of the usage chunk of a stream.
- The `chat_dispatch` and `stream` spend recorders of `LLMClient` give `track_request_spend` the cached prompt tokens.
- The failed-attempt recorder reads the cached prompt tokens from the usage of an error body, as it reads the prompt and completion tokens.

## Capabilities
- `ai-spend-pricing`: a chat call of `LLMClient` gives the cached prompt tokens of its reply to the ledger.

## Impact
- The ledger, `devops ai cost-report` and `devops_cli_ai_spend_usd_total` show a lower and correct cost for chat calls to hosted groups that cache prompts, such as the DeepSeek group.
- The direct Claude provider and Ollama do not change. The Claude provider reads only `usage.input_tokens`, and an Ollama call is local at 0 USD.

## Feasibility
- The premise holds on main at 5f75d256. The paths that record spend for a chat call are `_record_dispatch_spend` (`chat_dispatch`), the stream recorder (`stream`), `_record_cache_hit` (`chat_cache_hit`, 0 tokens) and `record_failed_attempt` in `ai/spend/transport.py`. Only the agent paths (`build_agent` and `record_run_spend`) gave `cache_read_tokens`.
- The new test `test_a_chat_call_on_the_deepseek_group_costs_its_cached_and_new_input_and_its_output` fails on main in all three cases with 0.10192 USD for each row, and passes with the change at 0.033477 USD.
- The OpenAI Python SDK 3.26.1 types the field as `CompletionUsage.prompt_tokens_details.cached_tokens` (`openai/types/completion_usage.py`). genai-prices 0.1.13 maps the same path to `cache_read_tokens` for OpenAI-compatible replies.

## Existing Tool Considered
- The OpenAI Python SDK parses the reply and the stream chunks. The change reads its typed field `prompt_tokens_details.cached_tokens`. The pricing registry and genai-prices already price `cache_read_tokens`.
- `genai_prices.extract_usage` reads the same field from a raw body, but it raises `LookupError` for a model that it does not know, such as a gateway route name. Thus the failed-attempt recorder reads the error body as a dict, as it does now for the prompt and completion tokens.
- The change deletes no internal code.
