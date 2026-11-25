# Proposal: #6762

## Why
`openspec/specs/rag-lookup-pause/spec.md` holds `qdrant-retry-wait-uses-clock-seam`, which names `tenacity` and gives three wait times (`0.5`, `1.0`, `1.5` seconds). `_execute_with_retry` (`src/devops_cli/ai/rag/qdrant.py:551-574`) uses a `for` loop with `_record_retry` (`sleep: Callable[[float], None] = clock_seam.sleep`) instead of `tenacity`, and `DEFAULT_MAX_RETRIES = 3` attempts make two waits (`0.5` and `1.0` seconds).

## What Changes
- Remove `qdrant-retry-wait-uses-clock-seam` from `openspec/specs/rag-lookup-pause/spec.md`.
- Add `qdrant-retry-wait-uses-clock-seam` to `openspec/specs/qdrant-request-retry/spec.md`, naming the `sleep` parameter supplied by the clock seam without `tenacity` and giving the two waits (`0.5` and `1.0` seconds) for three attempts.
- Add spec verification tests in `tests/openspec/test_qdrant_retry_spec.py`.

## Capabilities
- Removed from `rag-lookup-pause`: `qdrant-retry-wait-uses-clock-seam`
- Added to `qdrant-request-retry`: `qdrant-retry-wait-uses-clock-seam`

## Impact
- `openspec/specs/rag-lookup-pause/spec.md`
- `openspec/specs/qdrant-request-retry/spec.md`
- `tests/openspec/test_qdrant_retry_spec.py`

Fits in one pull request.

## Feasibility
Confirmed on `origin/main`:
- `openspec/specs/rag-lookup-pause/spec.md:26-35` names `tenacity` and waits `0.5, 1.0, and 1.5 seconds`.
- `src/devops_cli/ai/rag/qdrant.py:197-232,551-574` loops over `max_attempts: int = DEFAULT_MAX_RETRIES` (`3`, `src/devops_cli/config/defaults.py:570`) and sleeps `0.5 * attempt` via `sleep` (`clock_seam.sleep`) before attempt 2 (`0.5`) and attempt 3 (`1.0`).
- `tests/ai/rag/test_qdrant_request_telemetry.py:117-126` asserts `clock.waits == [0.5, 1.0]`.

## Existing Tool Considered
No new tool or library applies; this change updates OpenSpec prose and tests (`alternatives.verdict: not-applicable`). Zero implementation build cost beyond documentation and test edits.
