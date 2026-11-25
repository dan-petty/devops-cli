# Design

## Decisions
- Put the shared clear key tuples and `run_clear_marks()` helper in `src/devops_cli/roadmap/implement/record_clear.py` importing only `ImplementRecordKey` from `store.py`, avoiding import cycles across `stage.py`, `return_item.py`, `implement_report.py`, and `review.py`.
- Pass `run_clear_marks()` inside the single write of `_reject_plan` (`stage.py`) so both the `staged=True` and `staged=False` rejection branches clear stale implement run keys atomically alongside `STAGE_PLAN_KEYS` and `stage.rejected`.
- Merge `run_clear_marks()` inside `apply_return` (`return_item.py`) when `clear_implement=True` (default for manual returns), and pass `clear_implement=False` from `implement_report.return_to_new` so an in-flight runner pod keeps `implement.job` until `implement_submit._report` finishes reporting spend and result lines.
- Keep `implement.digest_clears`, `implement.continuations`, `implement.spend`, `implement.spend_counted`, and `implement.trace` out of `RUN_CLEAR_KEYS` so return/rejection preserves non-run accounting and continuation history.
- Switch `stage_ready._recorded_pull` and `fix_plan._record_reason` from checking `ImplementRecordKey.JOB` directly to `job_holds(item)`.

## Rejected alternatives
- **Clear only `implement.stopped` and `implement.failure`**: leaves stale `implement.branch`, `implement.pr`, and `implement.job`, which still misroute `implement` and `stage_ready`.
- **Clear all `ImplementRecordKey` members**: erases continuation and spend accounting history across runs.
- **Keep raw `implement.job` checks in `stage_ready` and `fix_plan`**: finished runner Jobs keep `implement.job` alongside `implement.job_state`, hiding subsequent drafts.
