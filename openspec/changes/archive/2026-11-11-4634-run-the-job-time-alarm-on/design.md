# Design

## Decisions

- The time of a run is the run time of the slowest shard job plus the run time of the join job. The shards run side by side, and the join starts after the last of them (`needs: test-shard`). With a free runner for each job, this is the time that a person waits for the check. The rest of the span, from the first start of a shard to the end of the join, is time in the queue.
- The queue time is a field of `JobRunTime` (`queue_seconds`, default 0). The report gives its mean, and the command prints it in a column of the table and on its own line before the verdict. The limit applies only to the run time, so a busy account does not turn the alarm red, and a slow test still does.
- A run with no shard job is timed by the join job alone, as before, with a queue time of 0.
- `_JobTiming.ran_seconds` gives the run time of one job, or None when GitHub gives no start or no end. A shard without both is left out of the slowest shard, as a skipped shard is.
- The job `job-time` runs on `schedule` and `workflow_dispatch`. A merge changes one run of the window of 20, so a daily read shows the same trend. The push run of `main` then shows only the result of its own checks.
- The concurrency group is `ci-${{ github.workflow }}-${{ github.event_name }}-${{ github.ref }}`. Pull request runs, push runs, schedule runs and manual runs each get their own group, and each kind still cancels its own older run.

## Rejected alternatives

- Keep the job on push and mark it `continue-on-error`: rejected. The run turns green, but the alarm then fails in silence, and the job still takes a runner on each merge.
- Time each run from the `created_at` of the jobs: rejected. That adds the queue time; the issue asks to remove it.
- Sum the run time of all shards: rejected. That is runner time, not the time that a person waits, and it grows with each new shard.
- A separate workflow file for the alarm: rejected. The schedule of `ci.yml` exists already, and a new file adds a workflow to keep for one job.
