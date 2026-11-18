# Proposal: #4927

## Why

`devops pr monitor` reported a pull request as ready while one of its checks had failed. The last
poll read no check at all (`Checks: 0/0 passed (0/0 done)`) and the monitor took the empty list as
success. At that time the check run `DevContainer Image` of the head commit had the conclusion
`failure`. `_judge_checks` in `src/devops_cli/github/merge_readiness.py` returns with no blocker
when `head_sha` is empty, and `get_pr_monitoring_status` sets `head_sha` to `""` when the pull
request read gives no `head.sha`. The verdict then reads no check and holds no blocker, so it
reports the pull request as ready. Closes #4927.

## What Changes

- `_judge_checks` holds a `checks_unread` blocker when the pull request payload gives no head
  commit SHA, so the verdict never reports ready with no read of the checks.
- `devops pr ready`, `devops pr check-readiness` and `devops pr monitor` fail closed through the
  one verdict: the monitor sets `checks_failed` and exits 1.

## Capabilities

`pr-merge-readiness` (modified): a poll with no head commit is a poll with no data and fails closed.

## Impact

- A poll that reads no head commit no longer reports ready.
- A commit that reports no check where a workflow can start one keeps its pending wait (#6173).
- The change fits one pull request.

## Feasibility

- Read 2026-11-18: `assess_merge_readiness` reads `head_sha` from `head.sha` of the payload
  (`src/devops_cli/github/merge_readiness.py:709`), and `_judge_checks` returns with no blocker when
  it is empty. `CHECKS_UNREAD` is already a failure kind (`CHECK_FAILURE_KINDS`), so the monitor
  maps it to `checks_failed` and exit 1 with no other change
  (`src/devops_cli/github/pr_monitor.py:572`).

## Existing Tool Considered

No new tool is needed. The 2026-11-15 alternatives check found no library that gives a
merge-readiness verdict over the check runs of the head commit or that fails closed on an empty
read. The fix is a few lines in `_judge_checks`.
