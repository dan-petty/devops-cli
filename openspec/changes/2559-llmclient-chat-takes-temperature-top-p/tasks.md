# Tasks

## 1. Add explicit sampling params to chat and chat_messages

Reads: none. Changes: `src/devops_cli/ai/client/unified.py`, `tests/ai/client/test_unified_sampling.py`.

- [ ] 1.1 Write a test that calls client.chat('sys', 'user', temperature=0.9, seed=7) with a fake httpx2 transport. Assert the request body contains temperature 0.9 and seed 7. Write a test that calls client.chat('sys', 'user', unknown_param=1) and asserts TypeError is raised. Write a test that calls client.chat('sys', 'user') with config temperature 0.1 and asserts the request body contains temperature 0.1, and verify that `uv run devops ci test tests/ai/client/test_unified_sampling.py` fails on the base
- [ ] 1.2 In chat(), replace **kwargs: Any with temperature: float | None = None, top_p: float | None = None, seed: int | None = None. Pass them to chat_messages(). In chat_messages(), replace **kwargs: Any with the same three parameters. Thread them through _retry_chat_dispatch (add as keyword args), _dispatch_messages (add as keyword args), and _invoke_provider_messages (add as keyword args). In cache_opts, use the per-call value when not None, else the config value. In _dispatch_messages telemetry, use the per-call value when not None, else the config value, and verify that `uv run devops ci test tests/ai/client/test_unified_sampling.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Use per-call sampling in provider payload builders

Reads: none. Changes: `src/devops_cli/ai/client/openai.py`, `src/devops_cli/ai/client/ollama.py`, `src/devops_cli/ai/client/claude.py`, `tests/ai/client/test_provider_sampling.py`.

- [ ] 2.1 Write a test that builds an LLMClient with provider openai and config temperature 0.1. Call chat with temperature=0.9. Assert the HTTP request body has temperature 0.9. Write a test with provider ollama and the same assertion. Write a test with provider claude and config temperature 0.1. Call chat with temperature=0.9 and seed=7. Assert the request body has temperature 0.9 and no seed key, and verify that `uv run devops ci test tests/ai/client/test_provider_sampling.py` fails on the base
- [ ] 2.2 In _openai_compat_messages, _ollama_messages, and _claude_messages, accept temperature, top_p, and seed as keyword arguments. Pass them to _apply_sampling_and_limits (openai), the Ollama options dict (ollama), and the Claude message body (claude). In each builder, use the per-call value when not None, else fall back to self._config.temperature or self._config.top_p. In the Claude builder, omit seed from the payload entirely, as the Anthropic API does not accept it, and verify that `uv run devops ci test tests/ai/client/test_provider_sampling.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Cache key includes per-call sampling values

Reads: none. Changes: `tests/ai/client/test_cache_key_sampling.py`.

- [ ] 3.1 Write a test that calls chat with temperature=0.1 and then temperature=0.9 for the same system and user text. Assert the two calls produce different cache keys. Write a test that calls chat with seed=7 and then seed=42. Assert the two calls produce different cache keys. Write a test that calls chat with no sampling params and asserts the cache key matches the config-based key, and verify that `uv run devops ci test tests/ai/client/test_cache_key_sampling.py` fails on the base
- [ ] 3.2 Verify that the cache_opts dict in chat_messages() already uses the per-call values threaded in Group 1. If the cache key generation in self._cache.generate_key does not include seed, add seed to the options dict passed to generate_key. Confirm the existing cache key logic in src/devops_cli/ai/response_cache.py hashes the options dict, so a change in any option value changes the key, and verify that `uv run devops ci test tests/ai/client/test_cache_key_sampling.py` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
