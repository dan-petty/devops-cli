# Tasks

## 1. Key the Valkey vector by the request identity

Reads: `src/devops_cli/ai/rag/embeddings.py`. Changes: the same file and `tests/ai/rag/test_embedding_cache.py`.

- [ ] 1.1 Hash `_disk_cache_model()` in `_valkey_key`.
- [ ] 1.2 Add the direct/gateway test.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_embedding_cache.py tests/ai/rag/test_embedding_disk_cache.py` passes
