# Tasks

## 1. Failing tests

- [x] Add failing test in `tests/test_ai_client_providers_and_embeddings.py` verifying `openai` provider without `api_base_url` sends requests to `/v1` routes for unstreamed chat, streamed chat, and model listing <!-- id: 0 -->
  - Verification: `uv run devops ci test tests/test_ai_client_providers_and_embeddings.py -k test_openai_default_routes_use_v1`
- [x] Add failing test in `tests/test_ai_client_providers_and_embeddings.py` verifying SDK client uses factory HTTP client identity <!-- id: 1 -->
  - Verification: `uv run devops ci test tests/test_ai_client_providers_and_embeddings.py -k test_openai_sdk_client_uses_factory_transport`

## 2. Implementation

- [x] Update `OpenAICompatProviderMixin` in `src/devops_cli/ai/client/openai.py` with `openai.OpenAI` integration and error mapping <!-- id: 2 -->
  - Verification: `uv run devops ci test tests/test_ai_client_providers_and_embeddings.py`
- [x] Remove `_openai_stream_frame` from `src/devops_cli/ai/client/streaming.py` and delete hand-written payload builders <!-- id: 3 -->
  - Verification: `git grep "_openai_stream_frame" src/` returns nothing
- [x] Remove `CONST_URL_OPENAI_API_BASE` and update references in `constants.py`, `unified.py`, `endpoints.py`, and `embeddings.py` <!-- id: 4 -->
  - Verification: `git grep "CONST_URL_OPENAI_API_BASE" src/` returns nothing
- [x] Update existing tests referencing deleted constants or frames <!-- id: 5 -->
  - Verification: `uv run devops ci test tests/test_ai_streaming.py tests/test_thinking_providers.py tests/test_ai_benchmark.py`

## 3. Verification and checks

- [x] Verify `fail-to-pass` check run against base <!-- id: 6 -->
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Verify full CI checks pass <!-- id: 7 -->
  - Verification: `uv run devops ci`
- [x] Archive OpenSpec change <!-- id: 8 -->
  - Verification: `uv run devops openspec archive 1427-openai-provider-routes`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
