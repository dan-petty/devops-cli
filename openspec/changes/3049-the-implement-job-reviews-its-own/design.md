# Design

## Decisions

- **Run the review after the last task group and the push, before `gh pr ready`, and gate `_ready` on it.**: The review must see the final head, and the issue requires the ready mark to wait for both the checks and the review.
- **Treat a high-severity finding as repaired after one fix step and a re-run, and block the item when it survives.**: CONTEXT.md's Implementing definition allows at most one fix step, so the job gets one chance to fix before it blocks.
- **State the review budget as two runs per item in the `roadmap.implement.review_runs` setting.**: One initial run and one re-run after the repair round bound the cost, and the setting makes the budget visible and enforceable.
- **Write the review result as the input of `ready_to_mark` in `src/devops_cli/roadmap/stage_ready.py`.**: That function is already the one seam of the ready decision, and #2867 replaces its body without touching a caller.
- **Post one comment line per finding with its disposition, under the existing comment marker.**: The implement comment already carries the outcome of each step, and one marker keeps a single comment per run.

## Rejected alternatives

- **Block the item at the first high-severity finding with no repair round.**: CONTEXT.md's Implementing definition gives at most one fix step, so a fixable finding would stop an item that the job could repair.
- **Run the review only after `gh pr ready`, as an advisory.**: The issue's acceptance criterion says the ready mark waits for both the checks and the review, and that a high-severity finding blocks the ready mark.
- **Let the job call `devops review` without a budget.**: The issue requires the review call budget per item to be stated and enforced, and ADR 0005 records that extra review calls did not raise precision.
- **Build a review engine into the implement job.**: ADR 0005 already moved findings to pinned tools, advisories, confirmed facts and the rule pack, and `devops review` ships them.
