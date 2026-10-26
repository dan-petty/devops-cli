# Tasks

## 1. Response cache directory confinement and key validation

- [x] 1.1 Write failing tests in `tests/test_response_cache.py` asserting that keys must be `llm_` followed by 64 hexadecimal characters, that malformed keys (`../x`, `/abs/x`, non-hex) are rejected before any filesystem access, that entries on disk with mismatched keys are deleted and not served, and that `delete()` removes entries from memory and disk. Verify with `uv run devops ci test tests/test_response_cache.py`.
- [x] 1.2 Implement `is_valid_cache_key`, strict key validation before disk operations, key equality verification on disk load, and `delete()` in `src/devops_cli/ai/response_cache.py`. Update existing tests in `tests/test_response_cache.py` that used arbitrary non-hex keys. Verify with `uv run devops ci test tests/test_response_cache.py` and `uv run mypy src/devops_cli/ai/response_cache.py`.
- [x] 1.3 Regenerate CLI documentation. Verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`.

## 2. Response cache configuration and singleton alignment

- [x] 2.1 Write failing tests in `tests/test_response_cache.py` asserting that the cache directory resolves under `<DATA_DIR>/cache/llm`, that `devops ai cache status` and `devops ai cache clear` read settings, and that a client initialized with `cache_enabled=False` neither reads nor writes the cache even when a singleton cache exists. Verify with `uv run devops ci test tests/test_response_cache.py`.
- [x] 2.2 Remove `dir` from `AICacheConfig` in `src/devops_cli/config/settings.py` and remove `DEFAULT_LLM_CACHE_DATA_DIR` in `src/devops_cli/config/defaults.py`. Update `get_llm_response_cache()` and `_resolve_llm_cache()` in `src/devops_cli/ai/client/unified.py` to build from settings and isolate disabled clients. Update `isolate_llm_response_cache` in `tests/conftest.py` to build via settings and request `isolate_data_dir`. Verify with `uv run devops ci test tests/test_response_cache.py tests/test_data_dir_configuration.py`.
- [x] 2.3 Regenerate CLI documentation. Verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`.

## 3. Client caching exclusions, rejected entry cleanup, and structured schema enforcement

- [ ] 3.1 Write failing tests in `tests/test_response_cache.py`, `tests/test_ai_client_structured.py`, and `tests/test_review_untrusted_tree.py` asserting that empty content replies with thinking blocks are not cached, that rejected lookups delete the entry from memory and disk, that `ModelProposal` forbids extra fields and requires `priority`, `value`, and `effort`, that structured replies failing schema validation are not cached, and that a clone tracking `.data/cache/llm/` files does not serve planted replies. Verify with `uv run devops ci test tests/test_response_cache.py tests/test_ai_client_structured.py tests/test_review_untrusted_tree.py`.
- [ ] 3.2 Update `_check_chat_cache` and `_handle_successful_chat_dispatch` in `src/devops_cli/ai/client/unified.py` to delete rejected lookup entries and bypass caching for empty responses. Update `ModelProposal` in `src/devops_cli/roadmap/intake_model.py` with `extra="forbid"` and required fields. Verify with `uv run devops ci test tests/test_response_cache.py tests/test_ai_client_structured.py tests/test_roadmap_intake.py tests/test_review_untrusted_tree.py`.
- [ ] 3.3 Regenerate CLI documentation and verify full suite. Verify with `uv run devops docs generate --sync-readme`, `uv run devops docs check`, and `uv run devops ci`.

## Workflow follow-up

- Pending a person: run `devops ai review branch` from inside a scratch clone that tracks a `.data/cache/llm` directory and verify no file under the clone's `.data/` is created or modified.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
