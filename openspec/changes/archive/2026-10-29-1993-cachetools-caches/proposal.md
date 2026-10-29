# Proposal

## Why

Issue #1993: three in-process caches are hand-written or unbounded.

- The embedding LRU cache (`_EmbeddingLRUCache`, `src/devops_cli/ai/rag/embeddings.py`) and the webhook replay guard (`DeliveryLRUCache`, `src/devops_cli/server/routes/webhooks.py`) each keep an `OrderedDict` with their own eviction.
- The memory cache of `CloudflareRadarClient` (`src/devops_cli/security/vulnerability_lookup.py`) is a plain `dict` with no bound and no expiry. In a long-running process, such as the roadmap Service, it grows with each domain and never asks Radar again.

## What Changes

- `_EmbeddingLRUCache` keeps its interface, lock and hit and miss counters, and stores its vectors in a `cachetools.LRUCache` of the same size (`DEFAULT_RAG_EMBEDDING_CACHE_SIZE` or the engine's `cache_size`, at least 1).
- `DeliveryLRUCache` keeps its interface and lock, and stores the delivery ids in a `cachetools.LRUCache` of `CONST_SERVICE_DELIVERY_LRU_CAPACITY` (10,000) entries. A repeated id is still refused and moves to the most recent place.
- The memory cache of `CloudflareRadarClient` is a `cachetools.TTLCache` of at most 1,000 records (`_MAX_RADAR_CACHE_SIZE`, the bound of the OSV cache in the same module), whose entries expire after the client's threat-intel TTL (`valkey.threat_intel_ttl`, 86,400 s by default, or the `ttl` argument). The cache reads time through the clock seam `devops_cli.core.clock.monotonic`, so a test moves time with the `clock` fixture.
- Behavior that a consumer observes changes only for the Radar cache, so the change carries one ADDED requirement in `valkey-cache-tier`.
- The `OrderedDict` of the OSV client stays; #1146 owns it.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `valkey-cache-tier`: the threat-intel memory tier has a bound and an expiry.

## Impact

- `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/security/vulnerability_lookup.py`.
- `tests/test_security_threat_intel.py`, `tests/test_server_service.py`.

## Feasibility

- `cachetools` 7.1.8 is a pinned direct dependency (`pyproject.toml`) and ships `py.typed`. `src/devops_cli/github/session_transport.py` already uses its `LRUCache`.
- Checked in the installed 7.1.8: `LRUCache.get` and an overwrite move a key to the most recent place, and an insert at `maxsize` evicts the least recently used key, as the two `OrderedDict` caches do. `TTLCache(maxsize, ttl, timer=...)` keeps at most `maxsize` entries, and a key reads as absent once `timer()` reaches its insert time plus `ttl`.
- cachetools caches are not thread-safe. Each cache stays under the lock it has today: every read and write of the three caches already runs under that lock.
- The hit and miss counters of `_EmbeddingLRUCache` have no reader in `src`; the embedding cache metric is counted from the engine's partition (#817). The issue asks to keep them, so they stay.

## Existing Tool Considered

`cachetools` (`LRUCache`, `TTLCache`), already a pinned dependency. The change deletes the two hand-written `OrderedDict` evictions and builds nothing.
