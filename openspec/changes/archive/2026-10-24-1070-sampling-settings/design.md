# Design

## Context

See `proposal.md` for motivation and background. LLM inference parameters in `devops-cli` are configured globally in `AIConfig` and per task in `AITaskOverride`. Review pipelines execute multiple tasks (`analysis`, `verification`, `compose`) across different providers (`gateway`, `ollama`, `openai`, `copilot`, `claude`). Responses are cached in `LLMResponseCache` using SHA-256 keys generated from the request attributes.

## Goals / Non-Goals

**Goals:**
- Ensure all configured sampling settings reliably reach inference backends or are rejected with informative errors.
- Disallow undeclared configuration keys under `ai` and `ai.tasks` while explaining where per-model parameters reside.
- Provide parity between streamed and unstreamed requests for both OpenAI-compatible and native Ollama clients.
- Allow tasks to opt out of client-side temperature/top_p overrides to respect model card defaults.
- Record active models and sampling parameters in `profile.json` for all review sessions.
- Invalidate cache entries when sampling parameters change.

**Non-Goals:**
- Reasoning parameter mapping for gateway thinking mode (handled in #888).
- Cache admission policies (handled in #1013).
- Model residency and backend `keep_alive` controls (handled in #598 and #1064).

## Decisions

### 1. Refuse `num_ctx` on non-Ollama providers in `LLMClient`
`LLMClient` validates the resolved `AIConfig` on initialization and when `get_context_window(task)` is queried. If `num_ctx` is set and the provider is `gateway` or an OpenAI-compatible provider (`openai`, `copilot`), it raises `ConfigurationError` naming the task and explaining that server context is configured via the tier's `OLLAMA_CONTEXT_LENGTH` and page sizing is controlled by `context_window`.
- *Alternative considered*: Silently ignoring `num_ctx` or attempting to pass it in extra body parameters.
- *Evidence rejecting alternative*: Passing disparate context sizes to Ollama backends causes Ollama to reload model weights, causing thrashing on shared single-slot GPU tiers. OpenAI and LiteLLM APIs do not recognize `num_ctx`.

### 2. Forbid unknown keys in `AIConfig`, `AITasksConfig`, and `AITaskOverride`
Set `extra="forbid"` on `AIConfig`, `AITasksConfig`, and `AITaskOverride`. In addition, a `mode="before"` model validator on `AIConfig` and `AITaskOverride` checks for extra keys: for the six per-model sampling keys (`top_k`, `min_p`, `presence_penalty`, `repeat_penalty`, `think`, `keep_alive`), the error states that these settings belong in a gateway deployment's `litellm_params` or the Ollama tag. Add `verification` and `compose` fields to `AITasksConfig` so review tasks can be explicitly configured.
- *Alternative considered*: Adding `top_k`, `min_p`, `presence_penalty`, and `repeat_penalty` directly as Pydantic fields on `AIConfig`.
- *Evidence rejecting alternative*: These parameters are model-specific rather than universal. A gateway task group like `devops-review` multiplexes diverse models (e.g. Qwen and GPT-OSS). Specifying model-specific knobs in client configs creates invalid parameter errors across heterogeneous backends.

### 3. Dedicated `use_model_sampling` boolean setting
Introduce `use_model_sampling: bool | None = None` on `AITaskOverride` and `use_model_sampling: bool = False` on `AIConfig`. When true, request builders omit `temperature` and `top_p`.
- *Alternative considered*: Allowing `temperature: null` in YAML to signify "no temperature".
- *Evidence rejecting alternative*: In Pydantic hierarchical task overrides, `None` denotes inheritance from the parent `AIConfig`. A separate boolean maintains unambiguous inheritance semantics.

### 4. Parity in streaming payloads and options
In `openai.py`, remove early returns on `stream=True` in `_apply_standard_params` so `temperature` and `top_p` are included. In `ollama.py`, update `_ollama_stream_request` to build the same `options` dictionary (`num_ctx`, `num_predict`, `temperature`, `top_p`) and inject trace context headers as `_ollama_chat_request`.
- *Alternative considered*: Keeping minimal stream payloads.
- *Evidence rejecting alternative*: Omitting options caused streamed requests to run with server defaults rather than configured sampling and reply token limits.

### 5. Review profile sampling recording
Update `review_setup()` to return `models` and `sampling` for `analysis`, `verification`, and `compose`. For each task, `sampling` records `temperature`, `top_p`, `max_tokens`, `reasoning_effort`, and `use_model_sampling`, writing `None` (JSON `null`) for values not sent by the client. In `ReviewProfiler.build()`, populate `models` and `sampling` onto `ReviewProfile` so they are saved to `profile.json`.
- *Alternative considered*: Writing sampling only for benchmark runs.
- *Evidence rejecting alternative*: Review sessions from path, branch, and PR reviews lacked sampling provenance, making it impossible to audit differences across model versions.

### 6. Incorporate sampling into cache options
In `LLMClient._handle_chat_dispatch` / `unified.py`, pass `temperature`, `top_p`, `reasoning_effort`, and reply cap (`max_tokens` from `_completion_limit()`) into `options` passed to `_cache.generate_key`.
- *Alternative considered*: Continuing to pass only `enable_thinking`.
- *Evidence rejecting alternative*: Sampling parameter modifications replayed obsolete cached responses across review runs for 7 days.

## Risks / Trade-offs

- [Risk] Existing `config.yaml` files with obsolete keys will fail validation. → Mitigation: Per `AGENTS.md` and pre-1.0 rules, no shims are retained; error messages explicitly direct users to remove or relocate invalid keys.
- [Risk] Cache misses will increase after deploying the change due to the expanded key format. → Mitigation: One-time recomputation occurs as stale cache entries are superseded with correctly partitioned keys.
