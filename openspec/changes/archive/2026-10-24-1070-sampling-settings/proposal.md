# Proposal

## Why

Issue #1070: Several AI model sampling and serving settings either fail to reach the model or reach it without being tracked, impairing reproducible reviews and benchmark comparisons. Setting `ai.tasks.analysis.num_ctx` silently alters review page sizing without reaching the gateway server (which sizes context from `OLLAMA_CONTEXT_LENGTH`), while six per-model sampling keys (`top_k`, `min_p`, `presence_penalty`, `repeat_penalty`, `think`, `keep_alive`) are dropped silently because Pydantic ignored unknown keys. Furthermore, streamed calls in `openai.py` and `ollama.py` dropped sampling options and trace headers, task configurations lacked an option to defer sampling to the underlying model card, review sessions omitted sampling from `profile.json`, and the reply cache key omitted sampling parameters, replaying replies across different sampling configurations.

## What Changes

- Refuse `num_ctx` on gateway and OpenAI-compatible providers: `LLMClient` raises `ConfigurationError` naming the task when its resolved config sets `num_ctx`, informing the user that the server context comes from the tier's `OLLAMA_CONTEXT_LENGTH` and `context_window` sizes pages. Native Ollama continues to send `num_ctx`.
- Forbid unknown keys under `ai`, `ai.tasks`, and `ai.tasks.<task>`: `AITaskOverride`, `AITasksConfig`, and `AIConfig` enforce `extra="forbid"`. Any unknown key raises validation errors naming the key; for `top_k`, `min_p`, `presence_penalty`, `repeat_penalty`, `think`, and `keep_alive`, the error explains that these settings belong in a gateway deployment's `litellm_params` or the Ollama tag. `verification` and `compose` are added as declared fields of `AITasksConfig`.
- Ensure streamed calls send the same sampling parameters as unstreamed calls: `_build_compat_payload(..., stream=True)` in `openai.py` preserves `temperature` and `top_p`. In `ollama.py`, `_ollama_stream_request` sends the identical `options` and trace context headers as unstreamed calls.
- Add `use_model_sampling: bool | None = None` to `AITaskOverride` and `use_model_sampling: bool = False` to `AIConfig`: When true for a task, requests omit `temperature` and `top_p` on both gateway and native Ollama paths.
- Record review models and sampling in `profile.json`: `review_setup()` and `ReviewProfile` record `models` and `sampling` for `analysis`, `verification`, and `compose` tasks, including `temperature`, `top_p`, `max_tokens`, `reasoning_effort`, and `use_model_sampling`. Values not sent by the client are serialized as `null`.
- Include client-sent sampling parameters in the LLM reply cache key: `LLMClient` passes `temperature`, `top_p`, `reasoning_effort`, and `max_tokens` (reply cap) alongside `enable_thinking` in `options` to `LLMResponseCache.generate_key`.
- Update documentation in `docs/CONFIGURATION.md` and the knowledge base explaining provider setting propagation and per-model sampling locations.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ai-model-sampling`: Governs model sampling options, refusal of unsupported context settings on remote providers, inclusion of sampling in cache keys, and session recording in review profiles.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/ai/client/unified.py`, `src/devops_cli/ai/client/openai.py`, `src/devops_cli/ai/client/ollama.py`, `src/devops_cli/ai/run_store.py`, `src/devops_cli/ai/review/profile.py`, `src/devops_cli/commands/ai.py`.
- Documents: `docs/CONFIGURATION.md`, `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md`.
- Tests: `tests/test_ai_model_sampling.py`, `tests/test_run_store.py`, `tests/test_config_field_validation.py`.

## Feasibility

- `num_ctx` refusal: Checked in `src/devops_cli/ai/client/unified.py:222-252` and `src/devops_cli/ai/client/openai.py:93-107`. Neither LiteLLM proxy nor OpenAI-compatible `/chat/completions` API schema defines `num_ctx` as a valid chat completion request field; Ollama context lengths on the gateway backends are provisioned cluster-wide via `OLLAMA_CONTEXT_LENGTH` (e.g. `k8s/llm/profiles/ollama-profiles.yaml:12`). Client validation during `LLMClient` initialization and `get_context_window` reliably detects `num_ctx` when configured on non-Ollama providers.
- Strict Pydantic configuration: Checked in `src/devops_cli/config/settings.py:489, 522`. Adding `model_config = ConfigDict(extra="forbid", ...)` and a `@model_validator(mode="before")` on `AIConfig` and `AITaskOverride` intercepts unregistered keys and emits targeted guidance for the six per-model sampling keys.
- Streamed sampling parity: In `openai.py:99-100`, removing the early return on `stream=True` in `_apply_standard_params` passes `temperature` and `top_p` in streamed JSON payloads. In `ollama.py:451-474`, applying the options builder and `inject_trace_context` ensures streamed requests match unstreamed requests.
- Cache key sensitivity: In `unified.py:778-796`, `generate_key` hashes JSON-serialized `options`. Including `temperature`, `top_p`, `reasoning_effort`, and `max_tokens` ensures cache keys partition distinct sampling parameters.
- Profile recording: In `run_store.py:151-167` and `ReviewProfiler.build()`, extracting `models` and `sampling` for `analysis`, `verification`, and `compose` persists them into `profile.json`.
- All tests run offline using `httpx2.MockTransport` and take under 1 second each.

## Existing Tool Considered

- LiteLLM per-model configuration (`litellm_params`): Already used for server-side model configuration in `k8s/llm/` and LiteLLM gateway routing. Standard parameters (`temperature`, `top_p`, `max_tokens`, `reasoning_effort`) are supported in standard chat completion schemas, whereas model-specific sampling keys (`top_k`, `repeat_penalty`, `presence_penalty`, `min_p`) belong in deployment cards or Ollama model tags rather than client-side pipeline overrides.
- No compensating shims or secondary validation layers are added. Internal code dropping parameters in `_apply_standard_params` is removed.
