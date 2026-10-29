# Tasks

## 1. The caches of a process share one Valkey cache tier

- [x] Add failing tests: two engines, a Radar client and the `ai ingest` store hold one tier; a refusing Valkey is dialled one time by four caches; the tier waits 0.25 s, at most `valkey.timeout`, for a connection; a `valkey.url` that is not valid gives one warning and no tier
  - Verification: `uv run devops ci test tests/test_valkey_cache_tier.py`
- [x] Add `connect_timeout` to `ValkeyClient`, `DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS` to `defaults.py`, and `shared_cache_tier` with `reset_shared_cache_tier` to `valkey/cache.py`
  - Verification: `uv run devops ci test tests/test_valkey_cache_tier.py tests/test_valkey.py`
- [x] Use the shared tier in the embeddings engine, the Radar client and `devops ai ingest`; give `LibraryVectorStore` the tier; delete `_resolve_runtime_valkey_client`, `_symbol_cache_tier` and the three `except Exception` sites; reset the tier in the test floor; lower the swallowed-failure ceilings
  - Verification: `uv run devops ci test tests/test_library_vector_tier.py tests/test_rag_embeddings.py tests/test_security_threat_intel.py tests/test_swallowed_failures_ratchet.py tests/test_architectural_invariants.py`
- [x] Describe the connect wait of the cache in the `valkey.timeout` description, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1992-shared-valkey-cache-tier`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
