## Problem Description

`LLMClient.chat` and `chat_messages` (`src/devops_cli/ai/client/unified.py`) take `**kwargs` and use none of them. A caller that passes `temperature`, `top_p` or `seed` gets no error, and the request carries the sampling of the client's config instead. The payload builders read `self._config.temperature` and `self._config.top_p` (`ai/client/openai.py`, `ai/client/ollama.py`), and the cache key reads the same config.

Review group analysis passes `temperature`, `top_p` and `seed` from its `SamplingRecord` on each call (`src/devops_cli/review/analysis.py`, `_run_model_job`), so it believes it sets them. Found while fixing #2447, which makes the record name the analysis task's configured sampling.

## Reproduction Steps

1. Build an `LLMClient` whose config has `temperature: 0.1`.
2. Call `client.chat("system", "user", temperature=0.9, seed=7)` against a fake model at the HTTP edge.
3. Read the request body.

## Expected vs Actual Behavior

- Expected: the request carries `temperature` 0.9 and `seed` 7, or the call refuses an argument it does not support.
- Actual: the request carries `temperature` 0.1 and no seed, and no error is raised.

## Environment Diagnostics

origin/main d156ce7e (2026-10-28).

## Existing Tool Considered

The OpenAI-compatible API, Ollama and Anthropic take `temperature`, `top_p` and `seed` (Anthropic: no seed) per request. No new tool is needed: either pass them through to the payload and the cache key, or remove `**kwargs` so that an unknown argument is a `TypeError`.


Source: https://github.com/dan-petty/devops-cli/issues/2447

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=0f7bc266fd52ad4b6ad23bf65b710cd20c398b18 -->
## Proposed design

### Problem statement
LLMClient.chat and chat_messages accept **kwargs but silently ignore temperature, top_p, and seed. A caller that passes these values, such as the review analysis module, believes it sets per-call sampling, but the request carries the client's config defaults instead. No error is raised, so the wrong sampling is used and the cache key does not reflect the intended values.

### Acceptance criteria

### Requirement: Per-call sampling in request payload
When a caller passes temperature, top_p, or seed to chat or chat_messages, the HTTP request body SHALL carry those values.

#### Scenario: Caller passes temperature=0.9 and seed=7
- **WHEN** A caller invokes client.chat(system, user, temperature=0.9, seed=7) against a fake model at the HTTP edge
- **THEN** The request body contains temperature 0.9 and seed 7

### Requirement: Per-call sampling in cache key
The cache key generated for a chat call SHALL include the per-call temperature, top_p, and seed values when they are provided.

#### Scenario: Two calls differ only in temperature
- **WHEN** A caller invokes chat with temperature=0.1 and then with temperature=0.9 for the same system and user text
- **THEN** The two calls produce different cache keys

### Requirement: Config default fallback
When a caller does not pass a sampling parameter, the request SHALL use the value from the client's config.

#### Scenario: Caller omits temperature
- **WHEN** A caller invokes client.chat(system, user) with config temperature set to 0.1
- **THEN** The request body contains temperature 0.1

### Requirement: Unknown keyword argument rejected
A call to chat or chat_messages with a keyword argument that is not a recognized parameter SHALL raise TypeError.

#### Scenario: Caller passes an unrecognized keyword
- **WHEN** A caller invokes client.chat(system, user, unknown_param=1)
- **THEN** A TypeError is raised

### Requirement: Seed omitted for unsupported providers
When the provider does not support seed, the request body SHALL omit the seed field even if the caller passes one.

#### Scenario: Caller passes seed to a Claude provider
- **WHEN** A caller invokes client.chat(system, user, seed=7) with provider set to claude
- **THEN** The request body does not contain a seed field

### Existing Tool Considered
No new tool or library is needed. The OpenAI-compatible API, Ollama, and Anthropic APIs natively accept temperature, top_p, and seed per request (Anthropic does not accept seed). The fix threads the caller's values through the existing call chain to the HTTP payload and the cache key. The written cost of building this code is the change to two or three files in src/devops_cli/ai/client/ to add explicit parameters and pass them to the payload builders and cache key generation.

### Key questions
- **Should the fix pass per-call values through to the payload, or remove **kwargs so unknown arguments raise TypeError?**: Pass the values through. The review analysis module already passes temperature, top_p, and seed and expects them to reach the model. The OpenAI, Ollama, and Anthropic APIs all accept per-request sampling. Removing **kwargs would break existing callers that legitimately need per-call sampling. (best practice) [sources: src/devops_cli/review/analysis.py, src/devops_cli/ai/client/unified.py]
  - Chosen: Pass temperature, top_p, seed through to payload and cache key. Callers already pass these values and expect them to work. The provider APIs support per-request sampling. This is the standard pattern for LLM clients.
  - Rejected: Remove **kwargs so unknown arguments raise TypeError. This would break the review analysis module, which legitimately needs per-call sampling. It also removes the ability to set sampling per call, which the provider APIs support.
- **Which parameters does the fix cover?**: temperature, top_p, and seed. These are the three parameters that the body names and that the review analysis module passes. Anthropic does not accept seed, so seed is omitted for that provider. [sources: src/devops_cli/review/analysis.py, src/devops_cli/ai/client/unified.py]
- **Which files hold the code that must change?**: src/devops_cli/ai/client/unified.py holds chat, chat_messages, _retry_chat_dispatch, and _dispatch_messages. The payload builders in src/devops_cli/ai/client/openai.py and src/devops_cli/ai/client/ollama.py read self._config.temperature and self._config.top_p. The cache key is generated in chat_messages in unified.py. [sources: src/devops_cli/ai/client/unified.py, src/devops_cli/ai/client/openai.py, src/devops_cli/ai/client/ollama.py]
- **How should the per-call value interact with the config value in the payload builder?**: The per-call value takes precedence when it is not None. When it is None, the builder falls back to self._config.temperature or self._config.top_p. This preserves the existing behavior for callers that do not pass per-call values. (best practice) [sources: src/devops_cli/ai/client/unified.py]
  - Chosen: Per-call value overrides config when not None. This is the standard override pattern. It preserves existing behavior for callers that do not pass per-call values, and gives callers that do pass them the expected result.
  - Rejected: Per-call value replaces config entirely. This would require callers to pass all sampling parameters or get no sampling at all. It breaks existing callers that rely on config defaults.

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": null, "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "implement.branch": "fix/2559-llmclient-chat-takes-temperature-top-p", "implement.job": "devops-cli-runner-20261101-095702-76d0", "implement.job_digest": "sha256:59fd1dd8fc8586f5c4fc86d4fe6818fa0a6706468788fcfc6508544092eb788e", "implement.job_state": "succeeded", "implement.pr": "2997", "implement.spend": "{\"requests\": 80, \"input_tokens\": 2684174, \"output_tokens\": 11011}", "implement.stopped": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "481441ebc926686d59b2aab0737ada01c1e2cd10ef39825354d4850c48705207", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "747f59939616da63a7d396ad4cf54a4fe8da1d26f799d77690f360defa15b42f", "stage.branch": "fix/2559-llmclient-chat-takes-temperature-top-p", "stage.file_cap": null, "stage.groups": "[[\"Add explicit sampling params to chat and chat_messages\", 4757], [\"Use per-call sampling in provider payload builders\", 4758], [\"Cache key includes per-call sampling values\", 4678]]", "stage.needs_split": null, "stage.pr": "2997", "stage.sha": "bf0935911a93da1a804d67c10d627bc6cf89bbb3"} -->
