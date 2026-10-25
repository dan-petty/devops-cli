# Proposal

## Why

Issue #1351: `investigate_rag_context` caches a failed lookup as `None` for 60 seconds.
After a transient failure, the same query returns `None` for up to 60 seconds even after the backend recovers.
Other queries can retrieve context while the failed query cannot.
The cache must store only completed lookups.
A failure, a pause, or a stop must not enter the cache.

## What Changes

- Cache lookup results in `_INVESTIGATION_CACHE` only when the lookup completes.
- Keep failures, pauses, and stops out of `_INVESTIGATION_CACHE`.
- Serve completed empty results from `_INVESTIGATION_CACHE`.
- Add a unit test verifying that a transient failure is not cached and an empty lookup is cached.
- This change alters no behavior that a consumer observes outside cache retention of failed lookups. The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/rag/investigator.py`: `investigate_rag_context` writes to `_INVESTIGATION_CACHE` only when `ctx is not None`.
- `tests/test_rag_investigator.py`: adds `test_transient_lookup_failure_is_not_cached_and_empty_lookup_is_served_from_cache`.

## Feasibility

- Code inspection at `origin/main` commit `5d368c8bf2b1efac5f54258a7cf456df2a90068c`: line 462 of `src/devops_cli/ai/rag/investigator.py` unconditionally assigns `_INVESTIGATION_CACHE[cache_key] = (now, found)`.
- When `_retrieve` returns `None` due to a transient error, timeout, or circuit breaker pause, `ctx` is `None` and `found` is `None`.
- The cache stores `(now, None)` for 60 seconds, preventing retries after the backend recovers.
- Runtime test: on unpatched code, a transient error followed by a hit for the same query returns `[False, False]`. With the fix, it returns `[False, True]`.

## Existing Tool Considered

`pybreaker` and the in-memory cache `_INVESTIGATION_CACHE` in `src/devops_cli/ai/rag/investigator.py` manage lookup retries and caching.
No open tool or external library is required for this bug fix.
Conditioning cache insertion on completed retrievals reuses the existing cache dictionary and circuit breaker.
