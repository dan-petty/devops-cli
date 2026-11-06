# Tasks

## 1. The built-in tool tests run on the shared fakes (behavior)

- [x] 1.1 Add the failing tests: the process tools on `process_fake`, the OSV, Shodan and Radar tools on `web`, and `rag_search` on `qdrant` and `embedder` (a found chunk, an empty store, a store that is down, an embedding failure, an unset address)
  - Verification: `uv run devops ci test tests/security/test_builtin_tools.py`
- [x] 1.2 Make `rag_search` take its client from `resolve_qdrant_client` and its embedder from `create_embedder`, add `embed_query` to `EmbedderProtocol` and `FakeEmbedder`, and add `seed_knowledge_base`
  - Verification: `uv run devops ci test tests/security/test_builtin_tools.py tests/ai/rag tests/config/test_setting_overrides_reach_their_readers.py`

## 2. The file holds no patch and no private import (refactor)

- [x] 2.1 Remove every patch, mock, `time.sleep` stub and private import from `tests/security/test_builtin_tools.py`
  - Verification: `! git grep -n -F -e unittest.mock -e MagicMock -e _run_tool_cmd -e _is_safe_workspace_path -e time.sleep -e setattr -e .patch -- tests/security/test_builtin_tools.py`
- [x] 2.2 Check that `rag_search` builds no client and no engine itself
  - Verification: `! git grep -n -e QdrantClient -e EmbeddingsEngine -- src/devops_cli/ai/tools`

## 3. Documents

- [x] 3.1 Describe `seed_knowledge_base`, the `rag_search` wiring and `embed_query` in `docs/TESTING.md`
  - Verification: `uv run devops ci docs`

## 4. Archive

- [x] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 3761-builtin-tool-tests-on-fakes`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
