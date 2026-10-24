# Tasks

## 1. Strict Configuration and Refusal of num_ctx

- [x] 1.1 Write failing unit tests for `num_ctx` refusal on gateway/OpenAI providers and unknown keys rejection under `ai` and `ai.tasks.<task>`: `uv run devops ci test tests/test_ai_model_sampling.py`
- [x] 1.2 Implement `num_ctx` refusal in `LLMClient` and strict `extra="forbid"` key validation with custom guidance in `AIConfig`, `AITasksConfig`, and `AITaskOverride`: `uv run devops ci test tests/test_ai_model_sampling.py`
- [x] 1.3 Update configuration documentation and descriptions: `uv run devops docs generate --sync-readme`

## 2. Streamed Sampling Parity and Model Sampling Flag

- [x] 2.1 Write failing unit tests for streamed OpenAI sampling retention, streamed native Ollama options and trace headers, and `use_model_sampling` behavior: `uv run devops ci test tests/test_ai_model_sampling.py`
- [x] 2.2 Implement streamed sampling retention in `openai.py`, streamed options/trace headers in `ollama.py`, and `use_model_sampling` support: `uv run devops ci test tests/test_ai_model_sampling.py`
- [x] 2.3 Update knowledge base documentation with model sampling guidance: `uv run devops docs generate --sync-readme`

## 3. Session Sampling Recording and Cache Key Sampling

- [x] 3.1 Write failing unit tests for `review_setup()` and `profile.json` recording `models` and `sampling` (analysis, verification, compose), and cache key variation across temperatures: `uv run devops ci test tests/test_ai_model_sampling.py`
- [x] 3.2 Implement `review_setup()`, `ReviewProfile`, and cache options inclusion in `unified.py`: `uv run devops ci test tests/test_ai_model_sampling.py`
- [x] 3.3 Update `tests/test_run_store.py` for the expanded `review_setup()` schema and regenerate docs: `uv run devops docs generate --sync-readme`

## Workflow follow-up

- Mapping `enable_thinking=False` to `think: true` on gateway is #888.
- Cache admission policy is #1013.
- Model residency and `keep_alive` are #598 and #1064.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
- Pending a person: run one pinned review after the change to verify `profile.json` shows 0.7 / 0.8 for analysis and verification.
