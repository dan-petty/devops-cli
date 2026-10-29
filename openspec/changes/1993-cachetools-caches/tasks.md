# Tasks

## 1. The caches use cachetools

- [x] Add failing tests: a Radar record expires after the client's TTL on the `clock` fixture, and a full Radar memory tier drops the least recently used record; a repeated delivery id within the capacity of the replay guard is refused, and the least recently used id leaves it at capacity
  - Verification: `uv run devops ci test tests/test_security_threat_intel.py tests/test_server_service.py`
- [x] Store the embedding vectors and the delivery ids in `cachetools.LRUCache`, and the Radar records in a `cachetools.TTLCache` on the clock seam, each under its existing lock; delete the `OrderedDict` evictions
  - Verification: `uv run devops ci test tests/test_rag_embeddings.py tests/test_security_threat_intel.py tests/test_server_service.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1993-cachetools-caches`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
