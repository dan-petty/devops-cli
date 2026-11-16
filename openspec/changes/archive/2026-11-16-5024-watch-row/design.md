# Design

## Decisions

### 1. Unified status-lane row `watch`
The `watch` row replaces `stage_ready` and `pr_conflicts` in `STATUS_LANE_ROWS`. It runs in the status lane without a repository clone, calls no language model, and executes on first run and every 3 minutes (`DEFAULT_ROADMAP_WATCH_INTERVAL_MINUTES`).

### 2. GraphQL batching with REST fallback
The row reads open roadmap pull requests using a single GraphQL query for the repository (`headRefOid`, `isDraft`, `mergeable`, `statusCheckRollup`, `baseRefName`, etc.). If a GraphQL budget hold occurs, it falls back to REST calls with conditional ETag caching.

### 3. Pure routing function `due_steps(state)`
The pure function `due_steps(state)` routes the pull request state:
- `READY`: triggers the `ready` step for bot pull requests (marking drafts ready).
- `CONFLICT`: posts one comment per head for person pull requests.
- `MERGED` or `CLOSED`: triggers Status sync and cleans up ledger entries (and plan cleanup if it is a plan).
- `FAILED` or `CONFLICT` on bot pull requests: writes no due marks (Owner Decision 2026-11-13 removes fix due marks; fix jobs run via their predicates).
- Pull requests with active runner units are skipped.

### 4. Watch ledger with 30-minute backoff
The watch row maintains a ledger `{pr, head, verdict, next_read_at}` saved to `watch.json` beside `schedule.json`. When a head fails, `next_read_at` is set to 30 minutes in the future. The row skips re-reading checks for that head until `next_read_at` expires or the head/base changes.

## Rejected alternatives

### Keep separate `stage_ready` and `pr_conflicts` rows
- Rejected: Separate rows duplicate polling overhead, lack unified backoff, and make multiple requests per tick.

### Keep fix-checks and fix-conflict due marks
- Rejected: Superseded by Owner Decision 2026-11-13 (pipeline split, tracker #5482 Phase 3), where fix jobs run via predicates rather than due marks.
