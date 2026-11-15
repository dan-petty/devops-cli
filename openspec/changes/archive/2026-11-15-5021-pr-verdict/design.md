# Design

## Decisions

- **Single Pure Verdict Function**: Implement `verdict(state)` in `src/devops_cli/roadmap/steps/watch.py` returning `WatchVerdict` with verdict enum: `PENDING`, `READY`, `FAILED`, `CONFLICT`, `BEHIND`, `THREADS`, `MERGED`, `CLOSED`, or `HEAD_MOVED`.
- **Skip CI Handling**: In accordance with the Owner decision of 2026-11-13 (#5482 Phase 3), heads with `[skip ci]` in the commit message receive no verdict (`None`).
- **Fail-Closed on Empty Checks (#4927)**: When a poll reads zero checks on a checked head, the verdict is `PENDING`, not ready.
- **Retry on Failed Read (#4838)**: Transient API errors during poll are logged as warnings and retried up to 3 consecutive failures before aborting.
- **One `mark_ready` Wrapper**: Consolidate `gh pr ready` execution into `src/devops_cli/roadmap/steps/ready.py`, enforcing that the head commit SHA matches the expected commit.
- **Architectural Guard**: Add an AST invariant test ensuring no module outside `steps/ready.py` runs `gh pr ready`.

## Rejected alternatives

- **Multiple Divergent Verdicts**: Keeping separate `_judge` implementations across `implement_pull`, `stage_ready`, `pr_conflicts`, and `pr_monitor` was rejected due to inconsistent state handling and premature readiness reporting.
- **Optimistic Ready on Empty Checks**: Treating zero check runs as immediate success was rejected because newly pushed commits often take several seconds for GitHub Actions to trigger.
