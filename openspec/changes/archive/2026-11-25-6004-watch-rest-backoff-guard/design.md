# Design

## Decisions
- Extract `_failed_head_in_backoff(ctx: _WatchContext, *, pr_number: int, head_sha: str, base_ref: str) -> bool` in `src/devops_cli/roadmap/watch_row.py` to test whether `ctx.recorded_pulls[pr_number]` is a `FAILED` entry with matching `head` and `base` and `ctx.current_time < datetime.fromisoformat(entry.next_read_at)`, recording `pr_number` in `ctx.failed_heads`.
- Call `_failed_head_in_backoff` inside `_process_rest_pulls` after resolving `(item, is_plan)` and before `read_check_runs`; when true, increment `ctx.watched_count += 1` and `continue` so zero check-run requests run and `WatchRoundResult.watched` / `WatchRoundResult.failed_heads` keep their GraphQL semantics.
- Reuse `_failed_head_in_backoff` in `_evaluate_pull` right after `ctx.watched_count += 1` so both paths share one predicate.

## Rejected alternatives
- **Keep backoff check only in `_evaluate_pull`**: `read_check_runs` still fires before `_evaluate_pull` is called in `_process_rest_pulls`.
- **Pass a lazy check-run reader into `_evaluate_pull`**: complicates `_evaluate_pull` and its callers for no gain over a shared pre-check helper.
