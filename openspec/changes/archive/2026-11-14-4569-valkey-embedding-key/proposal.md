# Proposal

## Why

The Valkey tier of the embedding cache keys each vector by the configured model and the text. A direct OpenAI request sends `text-embedding-3-small` (1,536 dimensions) for `qwen3-embedding:0.6b`, while the gateway sends the configured name (1,024 dimensions). Both runs share one key, so a gateway run can get a 1,536-dimension vector and `cosine_similarity` gives 0.0 (#4569).

## What Changes

- `_valkey_key` hashes the disk identity, which holds the provider and the request model name.
- A direct OpenAI vector is no hit for the gateway and the other way round.
- The disk and Valkey tiers share one identity.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `valkey-cache-tier`: The embedding key holds the provider and the request model.

## Impact

- Code: `src/devops_cli/ai/rag/embeddings.py`
- Tests: `tests/ai/rag/test_embedding_cache.py`

## Feasibility

- `_disk_cache_model` already gives the provider and the request model, and #4546 added it for the disk tier.
- The Valkey key is one hash.
- Verification commands: `uv run devops ci test tests/ai/rag/test_embedding_cache.py tests/ai/rag/test_embedding_disk_cache.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The Valkey client and the disk identity already exist. The change joins them and adds no library.
