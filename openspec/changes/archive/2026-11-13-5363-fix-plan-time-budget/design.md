# Design

## Decisions

- **Safe points.** The planner checks the budget before each plan run (`_ask_plan`) and each review run (`_review`). These are the points between model calls where the step holds no half-written state: the branch, the label and the record change only after `revise_plan` returns. The check raises `RoadmapTimeBudgetError`, and `revise_plan` turns it into a `StageFailure` through the same path as a failed model call, so the revision keeps the gated plan, the step and the findings of the review of the head.
- **The stop site passes the class.** `revise_plan` gives the failure of `RoadmapTimeBudgetError` the class `timeout`, as each stop site that knows its cause passes its class (#3476). `CLASS_BY_EXCEPTION` does not change: each class of that table needs a wait of the stage job in `RETRY_AFTER`, and the stage job has no budget.
- **No push on a timeout.** `_decide` puts `timeout` first. The step pushes no gated plan and no revision, also one that a review judged: the issue asks to keep the branch as it is, and the next attempt starts again from the head.
- **The comment keeps the label readable.** The `timeout` comment lists the open findings in the section that `comment_open_findings` reads, so the next attempt gives them to the planner as it does after a `stopped` comment. The comment goes on the issue, where every comment of the step goes, and names the plan pull request: `plan_comment` reads only the comments of the issue.
- **The record keeps the attempt.** The attempt marks stay as they are, so the 6-hour wait now follows a result line and a comment, not a stopped pod.
- **One progress line for each review.** A review ends each round, so the line follows it. `round` counts the reviews of the attempt, 0 for the review of the head, because `stage review round:` starts at 0 again in `_verified`. The line is a sibling of `stage review round:`, as `stage review extended:` is (#5066), so the documented fields of that line do not change. The stage job logs no progress line, because its planner has no budget.
- **The command writes the lines to stderr.** A Job runs the command, and its log is what the command writes. The handler covers only `round_log` and `job_result`, whose lines hold counts and names and no text of a model or an issue, and the command removes it after the call.
- **Default 3600 s.** It is below the 7200 s of the CronJob templates and the 5400 s of the hand-made Jobs, with a margin of 1200 s for one run that started before the end (757 s at most on #5350), the push and the comment. It is above the 3016 s of the longest attempt that repaired a plan.

## Rejected alternatives

- **`asyncio.timeout`.** The planner runs synchronously, so there is no event loop to cancel.
- **A signal or a watchdog thread that stops the process.** It can fire in the middle of a push, of a write of the record or of a comment, which is the state that the budget must not leave. A call that hangs is out of reach of the budget, and #5379 finds the cause of the one seen.
- **A check before each model request inside an agent run.** It needs a hook in `investigate`, which refine and the stage job share, and it stops a run halfway, whose tokens are then lost too. The margin for one run fits under the deadlines in force.
- **Push the gated plan or the revision that exists when the budget ends.** It writes the result of a part of the attempt, which the issue does not ask for. The rule of `regated` already pushes a gated plan when the attempt ends in time.
- **A `print_muted` line to stderr in the step, as the runner Job does.** The Service would then write each line twice, once as JSON and once as text.
