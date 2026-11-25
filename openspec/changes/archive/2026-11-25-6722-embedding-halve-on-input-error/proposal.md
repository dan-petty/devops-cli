# Proposal: #6722

## Why
With direct Ollama nodes, `_embed_batch_with_subdivision` in `src/devops_cli/ai/rag/embeddings.py` halves a batch after any `EmbeddingsError`, down to single texts. A permanent error such as HTTP 404 (unserved model), 401/403 (auth), 5xx, or a connect error gets the same error on every smaller batch, so a batch of 128 texts sends 255 requests before raising.

## What Changes
- Restrict `_embed_batch_with_subdivision` in `src/devops_cli/ai/rag/embeddings.py` so it halves a batch only when a node gave an input-refused HTTP status (400, 413, or 422), timed out (`TimeoutException` or `TimeoutError`), or gave an HTTP 200 reply with fewer vectors than texts.
- Raise `EmbeddingsError` immediately without halving on HTTP 401, 403, 404, 5xx, connect errors, unknown `EmbeddingsError` without a vector-count mismatch, or across-node failures with none of those halvable errors.
- Add fake-based unit tests in `tests/ai/rag/test_embedding_batching.py` and update `test_ollama_raises_after_every_node_fails` in `tests/ai/rag/test_embedding_provider_failures.py` to expect 2 node attempts instead of 4.

## Capabilities
- `embedding-batch-size`: Restrict direct Ollama batch subdivision to input-refusal statuses (400, 413, 422), timeouts, and malformed vector counts.

## Impact
- Prevents request amplification (~2n-1 requests per failed batch) during permanent/network failures on direct Ollama embedding backends and lets the indexer's circuit breaker trip at once.

## Feasibility
- Confirmed on `origin/main` (`4046839ec`): `src/devops_cli/ai/rag/embeddings.py:1130-1143` catches bare `EmbeddingsError` in `_embed_batch_with_subdivision` with no error-cause check, and `tests/ai/rag/test_embedding_provider_failures.py:76-104` asserts 4 requests when node 1 answers 404 and node 2 raises `ConnectError` on a 2-text batch. `is_input_refused_error` (`400`, `413`, `422`) and `EmbeddingsError.status` (added by #6717) are already present.

## Existing Tool Considered
No open library covers the project's internal Ollama batch-subdivision loop (confirmed in issue body alternatives check, verdict `none`). Cost to adjust in-place: ~50 lines across implementation and tests, ~1 hour.
