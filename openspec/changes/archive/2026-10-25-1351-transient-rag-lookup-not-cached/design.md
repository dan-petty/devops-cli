# Design

## Context

See `proposal.md` for motivation.
`investigate_rag_context` in `src/devops_cli/ai/rag/investigator.py` uses `_INVESTIGATION_CACHE` to memoize query results for 60 seconds.
When a retrieval encounters an error, `_retrieve` returns `None` or raises an exception.
The function previously cached `(now, found)` where `found` was `None`.
This caused transient failures to be cached, preventing recovery until the cache TTL expired.

## Goals / Non-Goals

**Goals:**

- Ensure that only completed lookups are added to `_INVESTIGATION_CACHE`.
- Ensure that hits and empty results alike are cached when the lookup completes.
- Ensure that transient failures, pauses, and stops are not cached.
- Allow queries to succeed immediately once the backend recovers from a transient failure.

**Non-Goals:**

- Do not alter the cache key format or the cache TTL duration.
- Do not alter circuit breaker behavior or probe coordination.
- Do not change how empty results are formatted or represented.

## Decisions

- **Condition cache insertion on `ctx is not None`.**
  When `_retrieve` succeeds, it returns a `RAGContext` instance (`ctx is not None`).
  If results are empty, `ctx.has_results` is `False`, `found` is `None`, and `(now, None)` is stored in the cache.
  If results are present, `found` is `ctx`, and `(now, ctx)` is stored in the cache.
  When `_retrieve` fails, pauses, or stops, `ctx` is `None`, and the function skips cache insertion.
  - *Rejected Alternative:* Clear cache on error. Evidence: Clearing the entire cache on an error purges valid cached lookups for other queries.
  - *Rejected Alternative:* Store an explicit status in the cache tuple. Evidence: Completed empty lookups return `None`, and failures do not cache. Checking `ctx is not None` before insertion avoids changing the cache tuple format.

## Risks / Trade-offs

- Repeated failed queries will call `_retrieve` until the circuit breaker trips. → This is the intended circuit breaker design. Three consecutive failures pause lookups for 60 seconds.
