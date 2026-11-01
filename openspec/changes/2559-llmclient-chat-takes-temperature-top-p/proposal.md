# Proposal

## Why

#2559: LLMClient.chat and chat_messages take **kwargs and use none of them. A caller that passes temperature, top_p, or seed gets no error, and the request carries the client config sampling instead. The review analysis module (src/devops_cli/review/analysis.py, _chat_and_judge) passes these values from its SamplingRecord on each call and believes it sets them.

## What Changes

- Replace **kwargs with explicit temperature, top_p, and seed parameters in chat() and chat_messages()
- Thread per-call sampling through _retry_chat_dispatch, _dispatch_messages, and _invoke_provider_messages
- Update provider payload builders (openai, ollama, claude) to use per-call values over config, with config fallback
- Omit seed in the Claude provider payload, as the Anthropic API does not accept it
- Include per-call temperature, top_p, and seed in the cache key when provided
- Raise TypeError when a caller passes an unrecognized keyword argument
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-model-sampling`: per-call-sampling-in-request-payload, per-call-sampling-in-cache-key, config-default-fallback, unknown-keyword-argument-rejected, seed-omitted-for-unsupported-providers

## Impact

- Code: `src/devops_cli/ai/client/unified.py`, `src/devops_cli/ai/client/openai.py`, `src/devops_cli/ai/client/ollama.py`, `src/devops_cli/ai/client/claude.py`
- Tests: `tests/ai/client/test_unified_sampling.py`, `tests/ai/client/test_provider_sampling.py`, `tests/ai/client/test_cache_key_sampling.py`

## Feasibility

- Confirmed: src/devops_cli/ai/client/unified.py line for chat() shows **kwargs: Any, and chat_messages() shows **kwargs: Any. Neither method reads temperature, top_p, or seed from kwargs.
- Confirmed: src/devops_cli/review/analysis.py _chat_and_judge calls llm_client.chat(..., temperature=sampling.temperature, top_p=sampling.top_p, seed=sampling.seed, ...), so the caller expects per-call sampling to work.
- Confirmed: src/devops_cli/ai/client/openai.py _apply_sampling_and_limits reads self._config.temperature and self._config.top_p, not per-call values.
- Confirmed: cache_opts in chat_messages() reads getattr(self._config, 'temperature', None) and getattr(self._config, 'top_p', None), not per-call values.
- First checks the implementation runs: (1) uv run devops ci test tests/ai/client/test_unified_sampling.py to verify per-call values reach the payload; (2) uv run devops ci test tests/ai/client/test_claude_seed.py to verify seed is omitted for Claude; (3) uv run devops ci test tests/ai/client/test_cache_key_sampling.py to verify cache key differentiation.

## Existing Tool Considered

No new tool is needed. The OpenAI-compatible API, Ollama, and Anthropic APIs natively accept temperature, top_p, and seed per request (Anthropic does not accept seed). The fix threads the caller's values through the existing call chain. The written cost is the change to four files in src/devops_cli/ai/client/ to add explicit parameters and pass them to the payload builders and cache key generation. No internal code is deleted; **kwargs is replaced by named parameters.
