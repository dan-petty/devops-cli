# Design

## Decisions

- **The entry of a step holds the counts of `StepOutcome`.** `_step_spend` copies `requests`, `input_tokens`, `output_tokens` and `repair_rounds` of the outcome. These are the counts that the totals of the record add, so the entries of one Job add up to the totals of that Job.
- **The largest request comes from the usage of each reply.** `_run_turn` takes the largest `usage.input_tokens` of the replies of a turn. `_Run.then` keeps the larger of two turns, and the step keeps the largest over its tiers. The value is the size of the largest request, because a request sends the whole conversation again.
- **The record holds counts only.** No path, command or text of the model goes into the entry.
- **The budget count stays.** `implement_limits.py` and the budget of a step and of the item do not change. #4387 changes the budget count in an open pull request.

## Rejected alternatives

- **Keep the cached and uncached input tokens apart in this change.** pydantic-ai gives `cache_read_tokens` for each reply, but the open pull request #4553 (#4387) adds `cache_read_tokens` to `StepOutcome`, `_Run` and `TierSpend` on the same lines. A second copy of the field would conflict with it. When #4553 is on main, `_step_spend` can write the field of the outcome in one line.
- **Read the figures from the trace.** The trace drops its oldest model events when a run is long (#4393), so a long run loses them. The record is not bound in this way.
- **A typed model for the entry of a step.** `_RecordedSpend.steps` is a list of dicts, and the readers use only some keys. A typed entry changes the readers of #4070 and #4394 and adds nothing to this change.
