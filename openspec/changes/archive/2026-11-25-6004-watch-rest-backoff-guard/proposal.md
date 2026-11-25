# Proposal: #6004

## Why
During a GraphQL quota hold, `_process_rest_pulls` in `src/devops_cli/roadmap/watch_row.py` calls `read_check_runs` before checking the 30-minute failed-head backoff recorded in the watch ledger. As a result, failed heads inside their backoff window trigger a REST check-runs request on every watch tick.

## What Changes
- Extract a shared `_failed_head_in_backoff` helper in `src/devops_cli/roadmap/watch_row.py`.
- Check the backoff before calling `read_check_runs` in `_process_rest_pulls`, appending to `ctx.failed_heads` and incrementing `ctx.watched_count` just as `_evaluate_pull` does, and skipping `read_check_runs`.
- Reuse `_failed_head_in_backoff` in `_evaluate_pull` so GraphQL and REST share one backoff rule.
- Add a unit test in `tests/roadmap/test_roadmap_watch_row.py` proving zero check-run reads when a failed head is in backoff during a GraphQL quota hold.

## Capabilities
- `roadmap-watch-row`: Enforce failed-head backoff before REST `read_check_runs` calls during GraphQL quota holds.

## Impact
- Prevents wasted GitHub REST API requests during GraphQL quota holds when failed PR heads are already backed off for 30 minutes.

## Feasibility
- Confirmed on `origin/main` (`4046839ec`): `src/devops_cli/roadmap/watch_row.py:851` invokes `read_check_runs(owner, name, pull_status.head_sha)` before `_evaluate_pull` checks `entry.verdict == PRVerdict.FAILED.value` (`lines 404-411`). `openspec/specs/roadmap-watch-row/spec.md:23` already specifies zero check re-reads within 30 minutes unless head or base moves.

## Existing Tool Considered
No external library governs internal `WatchLedger` backoff timing or REST fallback ordering (alternatives check verdict `none`). Reuses the existing backoff check via one helper in `watch_row.py`; ~25 lines, ~30 minutes.
