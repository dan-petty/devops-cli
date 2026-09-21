# Task 312: Valkey & Redis RESP3 Connection Pooling, Pipeline Batching & Tiered L1/L2 Cache Architecture Research

**Issue**: [#312](https://github.com/dan-petty/devops-cli/issues/312)
**PR**: [#356](https://github.com/dan-petty/devops-cli/pull/356)
**Status**: In Review
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Every cache read opened a fresh TCP connection and paid an `AUTH` round trip before the operation it was serving, and each command cost its own round trip. Cache helpers had grown independently across the AI, RAG, and review modules, each formatting its own key prefix and choosing its own TTL, so no namespace could be invalidated as a unit and two call sites could disagree about where a value lived.

### Key Deliverables Completed:

- [x] **Connection Pooling (`src/devops_cli/valkey/pool.py`)**:
  - Thread-safe bounded pool amortising TCP setup and authentication across callers, so a cache hit costs one round trip rather than three.
  - Idle connections past `DEFAULT_VALKEY_POOL_IDLE_TIMEOUT_SECONDS` are discarded rather than handed out, since a server-side timeout would otherwise surface as a mid-operation failure in the caller's code path.
  - A `connection()` context manager that discards rather than returns a connection when the block raises a connection error, because the socket state after such a failure is unknown.
  - A failed `connect()` frees its slot, so a refused endpoint cannot leak pool capacity.
  - `PoolStats` reporting created / reused / discarded counts and a reuse ratio.
- [x] **Pipeline Batching (`src/devops_cli/valkey/client.py`)**:
  - `pipeline()` writes an entire command batch in one `sendall` and reads all replies in order, collapsing N round trips into one.
  - `mget()` for bulk key reads preserving request order.
- [x] **Tiered L1/L2 Cache (`src/devops_cli/cache/tiered.py`)**:
  - `LRUCache` — bounded, thread-safe, TTL-aware in-process L1 with least-recently-*used* eviction.
  - `TieredCache` — reads L1, then L2, promoting an L2 hit into L1 so a repeat lookup within a command costs nothing.
  - `get_many()` fetches every L1 miss from L2 in a single `MGET`, which is the batching path for mass embedding and AST symbol lookups.
  - Every L2 failure degrades to a miss rather than propagating: a cache is an optimisation, and an unreachable one must not break the operation it was accelerating.
- [x] **Unified Key Namespacing & Invalidation**:
  - `build_cache_key` and `digest_key` are the single key builders, rooted at `CONST_CACHE_NAMESPACE_ROOT` so a shared Valkey instance stays partitioned per project.
  - `invalidate_namespace()` clears a logical group across both tiers — something the ad-hoc per-module prefixes could not express.
- [x] **`@cached` Decorator**: memoises a function through the tiered cache under a shared namespace, replacing the hand-written get/compute/set trios each module had grown. A `None` result is deliberately not cached, so a transient failure is retried.
- [x] **Legacy Elimination (`src/devops_cli/ai/cache/valkey_cache.py`)**:
  - Three near-identical get/set trios — each with its own `f"{PREFIX}{sha256(...)}"` formatting, JSON decode, and error handling — collapse onto the shared builder and tiered cache.
  - Embedding, finding, and LLM-response caches now share one key scheme, one TTL default (`DEFAULT_AI_CACHE_TTL_SECONDS`), and one statistics surface, and gain L1 caching for free.
  - New `get_embeddings()` batch accessor fetching many vectors in a single round trip.
- [x] **Cache Telemetry**: `CacheStats` separates L1 hits, L2 hits, misses, evictions, and writes, so each tier's contribution is individually visible rather than collapsed into one hit ratio.
- [x] **Automated Tests & Quality Gates**:
  - 31 unit tests in `tests/test_cache_tiered.py` plus new pipeline, `mget`, and provider tests, all using structural tuple equality assertions.
  - `pool.py` at 96%, `tiered.py` at 89% coverage.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ clean across all four touched modules.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## Verification Results

- `uv run devops ci` — all gates pass (tests, coverage $\ge 90\%$, lint, format, mypy strict, audit, security, actionlint, docs, uv check, lockfile).
- `devops scan complexity` clean on `cache/tiered.py`, `valkey/pool.py`, `valkey/client.py`, and `ai/cache/valkey_cache.py`.

## Design Note: `backend` Rather Than `pool`

`TieredCache` accepts any object exposing `execute(*parts)` — a `ValkeyConnectionPool` or a direct `ValkeyClient` both satisfy it. The parameter was initially named `pool`, which was misleading when a client was passed; it is now `backend`, with the duck-typed contract documented. This is what lets `ValkeyCacheProvider` keep its injectable-client constructor while still routing through the tiered cache.

## Scope Notes

**msgpack was not adopted.** The task suggested binary msgpack encoding to "eliminate redundant serialization overhead". Adding a dependency for it was not warranted: the measured cost here is network round trips, not serialization, which is exactly what pooling and batching address. JSON keeps cached values readable with `valkey-cli` during debugging. Revisiting this deserves a benchmark showing serialization is material, rather than an assumption.

**Distributed locking was not implemented.** `Redlock` is named in the task, but nothing in the codebase currently contends for a distributed lock, and a lock primitive with no consumer is speculative surface area — particularly one as easy to get subtly wrong as Redlock. `ValkeyClient.eval` already exposes the Lua path should a genuine need arise.
