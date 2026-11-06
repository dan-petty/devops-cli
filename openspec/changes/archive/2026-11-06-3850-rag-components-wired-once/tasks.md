# Tasks

## 1. One function wires the RAG components (behavior)

- [x] 1.1 Add `tests/ai/rag/test_rag_components.py`: the seams' clients, the default and configured collection names, the settings the caller gives, and the missing address. The tests fail on `origin/main` because `resolve_rag_components` does not exist.
  Verification: `uv run pytest tests/ai/rag/test_rag_components.py`
- [x] 1.2 Add `resolve_rag_components` and `RagComponents` to `ai/rag/indexer.py`, and give `resolve_qdrant_client` a `settings` argument.
  Verification: `uv run pytest tests/ai/rag/test_rag_components.py tests/ai/rag/test_qdrant_timeout_setting.py`
- [x] 1.3 Make `commands/rag.py`, `commands/ai.py` and `ai/rag/investigator.py` call it. Delete `_get_rag_components`, the pass-through `load_settings`, and the inline `QdrantClient` and `EmbeddingsEngine` of the investigator. Move the tests that patched these names to the Qdrant and embedder seams, and add the test of a missing address for each `devops ai rag` command.
  Verification: `uv run pytest tests/ai/rag/test_rag_cli.py tests/ai/rag/test_rag_investigator.py tests/ai/rag/test_rag_qdrant_server_label.py tests/git/test_ai_task_metadata.py`

## 2. One function builds the library vector store (behavior)

- [x] 2.1 Add `tests/ai/rag/test_library_store_wiring.py`: the dry run, the live store, an exact lookup, a Qdrant that does not answer, and a Qdrant that is not configured. Move the two build tests out of `tests/commands/test_library_vector_tier.py`. The tests fail on `origin/main` because `build_library_vector_store` does not exist.
  Verification: `uv run pytest tests/ai/rag/test_library_store_wiring.py`
- [x] 2.2 Add `build_library_vector_store` to `ai/rag/library_store.py`, and make `commands/ai_ingest.py` call it. Delete `build_runtime_vector_store`, `_build_runtime_vector_store`, `_resolve_runtime_qdrant_and_embedder` and the alias `_load_local_contracts`. Lower the swallowed-failure ceiling of `commands/ai_ingest.py`.
  Verification: `uv run pytest tests/ai/rag/test_library_store_wiring.py tests/commands/test_library_vector_tier.py tests/valkey/test_valkey_cache_tier.py`

## 3. No stale name remains (refactor that keeps behavior)

- [x] 3.1 Check that no file names a removed function.
  Verification: `! git grep -nw -e _get_rag_components -e build_runtime_vector_store -e _build_runtime_vector_store -e _load_local_contracts -e _resolve_runtime_qdrant_and_embedder -- src tests docs ':!docs/agent/archive' README.md ARCHITECTURE.md SECURITY.md k8s .github openspec/specs`
- [x] 3.2 Check that `commands/rag.py` defines no `load_settings`, and that the investigator builds no client.
  Verification: `! git grep -n -e "def load_settings" -e "EmbeddingsEngine(" -e "QdrantClient(" -- src/devops_cli/commands/rag.py src/devops_cli/ai/rag/investigator.py`

## 4. Documents (documents)

- [x] 4.1 Name `resolve_rag_components` and `build_library_vector_store` in the Qdrant item of `docs/TESTING.md`.
  Verification: `uv run devops ci --check --only docs`
- [x] 4.2 Check that the change folder is valid.
  Verification: `uv run devops openspec check`

## Workflow follow-up

- The other items of #1329 migrate the 23 `ai/rag` test files, the `ai/library` and command tests, and the docs ingester.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
