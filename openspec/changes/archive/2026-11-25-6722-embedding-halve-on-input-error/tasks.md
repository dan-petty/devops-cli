# Tasks

## 1. Behavior

- [x] 1.1 Add failing tests in `tests/ai/rag/test_embedding_batching.py` for halving on 400/413/422, not halving on 401/403/404/5xx/connect/unknown errors, and update `test_ollama_raises_after_every_node_fails` in `tests/ai/rag/test_embedding_provider_failures.py` to expect 2 requests across 2 nodes
  - Verification: `$ uv run devops ci test tests/ai/rag/test_embedding_batching.py tests/ai/rag/test_embedding_provider_failures.py`
- [x] 1.2 Gate `_embed_batch_with_subdivision` in `src/devops_cli/ai/rag/embeddings.py` on input-refused statuses (400, 413, 422), timeouts, and malformed 200 vector counts
  - Verification: `$ uv run devops ci test tests/ai/rag/test_embedding_batching.py tests/ai/rag/test_embedding_provider_failures.py`

## 2. Documents

- [x] 2.1 Validate OpenSpec change against existing embedding specs
  - Verification: `$ uv run devops openspec check`
