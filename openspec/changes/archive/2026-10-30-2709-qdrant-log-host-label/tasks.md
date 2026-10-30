# Tasks

## 1. Qdrant log lines, errors and cache key name the server by host and port

- [x] Add failing tests: the label of an HTTP URL, a Service address and a text with no origin; the `list_collections` and investigator log lines; the `InvalidURLError` text for four invalid URLs; the retriever cache key
  - Verification: `uv run devops ci test tests/test_rag_qdrant_server_label.py`
- [x] Add `qdrant_server_label` and `QdrantClient.server_label`, and use them in the two log lines and the cache key
  - Verification: `uv run devops ci test tests/test_rag_qdrant_server_label.py tests/test_rag_qdrant.py tests/test_rag_investigator.py tests/test_rag_indexer_retriever.py`
- [x] Make `InvalidURLError` name its server by label with the kind of problem kept, name `qdrant.url` in the Qdrant reason, and drop the URL from two reason texts of `validate_url`
  - Verification: `uv run devops ci test tests/test_rag_qdrant_server_label.py tests/test_validation.py tests/test_http.py`
- [x] Key the retriever cache by label, digest of the base URL and collection name, and add the collision tests
  - Verification: `uv run devops ci test tests/test_rag_qdrant_server_label.py tests/test_rag_indexer_retriever.py`
- [x] Regenerate the documentation that the change touches: it changes no command, option or MCP tool
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2709-qdrant-log-host-label`
