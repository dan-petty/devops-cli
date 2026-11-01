# Design

## Decisions

- **Change OLLAMA_KV_CACHE_TYPE from q4_0 to q8_0 on the ollama-16gib tier.**: All eight other tiers use q8_0. The 4-bit KV cache changes embedding vectors, so a RAG batch routed to the 16gib tier as an order-2 fallback puts drifted vectors into the shared Qdrant collection. Aligning the value removes the drift.
- **Do not add metadata to record which tier produced each vector.**: The proposed design in #2396 scopes this item to the one-line config fix. Recording the producing tier is a separate concern.

## Rejected alternatives

- **Remove the 16gib tier from the embedding group in the gateway config.**: The issue scopes the fix to the one-line config change. The 16gib tier is a valid order-2 fallback for embedding, and removing it reduces capacity.
- **Add per-vector tier metadata in the Qdrant collection.**: The proposed design in #2396 explicitly rejects this as a separate concern not part of this change.
