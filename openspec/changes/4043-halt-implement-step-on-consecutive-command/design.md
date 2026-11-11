# Design

## Decisions
- The count lives in `ToolCallLog` (`refused_run`). The log already sees each refused call, owns the total limit and ends a run with `UnexpectedModelBehavior`. `implement_step.py` is not changed.
- Only a call that returns and is not refused resets the count. A retry or a failed call neither adds nor resets: a retry is the model's own error and has its own limit.
- The consecutive stop fires at the third refusal, so the model does not see a third refusal. The total limit keeps its rule: the 31st refusal ends the run.
- The stop uses the failure class `refused_tool`, as the total stop does. The step halts; it does not change tier, as the next tier has the same shell policy.

## Rejected alternatives
- Count in `implement_step.py` after each turn: it misses refusals inside one turn.
- Replace the total limit: a model that alternates refused and accepted calls still burns tokens.
- A new failure class: the same root cause, one more mapping.
