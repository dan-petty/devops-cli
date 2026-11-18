# Design

## Decisions
- Guard in `_judge_checks`, the one place that reads the head commit's checks. `assess_merge_readiness`
  is the one verdict that `devops pr check-readiness`, `devops pr ready` and `devops pr monitor`
  share, so each caller fails closed.
- Use `BlockerKind.CHECKS_UNREAD`, the kind a failed check read uses. `CHECK_FAILURE_KINDS` already
  holds it, so `PRMonitorStatus.checks_failed` is True and the monitor exits 1 with no other change.
- The blocker text starts with `PR #<n> check verification failed closed:`, as the failed-read
  blocker does, so the reader sees one fail-closed line.

## Rejected alternatives
- Guard in `get_pr_monitoring_status`: it fixes the monitor only, and `devops pr ready` keeps the
  fail-open path.
- Guard in `_settled_result`: the verdict still calls the pull request ready, and only the monitor
  changes.
- A new `BlockerKind.CHECKS_EMPTY`: each caller maps blocker kinds to its own exit codes, so a new
  kind needs a mapping in each caller.
- `BlockerKind.CHECKS_FAILING`: no check failed in this case: the poll read no head commit.

## Superseded requirements
- The refine asked for a `checks_unread` blocker when a head commit with a SHA reports no check.
  That case is already decided: where a workflow can start a check, the verdict waits with
  `CHECKS_PENDING` (#6173, `test_a_commit_with_no_check_waits_while_a_pull_request_workflow_can_start_one`);
  where none can, `no_ci` holds (#5144). Both are newer than the refine, so they stay, and this
  change adds only the no-head-commit guard.
