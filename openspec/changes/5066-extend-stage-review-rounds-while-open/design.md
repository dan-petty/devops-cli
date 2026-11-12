# Design

## Decisions

- **A setting with a default of 2 and a hard ceiling of 4.**: The default keeps the cost of a plan at the defaults. The ceiling bounds the cost of an item at 21 plan runs and 5 review runs, as `CONST_ROADMAP_STAGE_GATE_RETURNS_CEILING` bounds the gate returns (#4900). The settings load refuses a value above it.
- **Extend only while the open count drops strictly.**: A drop from one review to the next shows that the planner fixes findings. A count that stays the same shows no progress, and a round then costs a plan run for no gain. The check compares two counts, so it makes no model call and gives the same answer each time.
- **The ceiling also bounds the extension.**: The loop runs at most `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING` rounds, and `repair_round_due` refuses a round past it, so no ConfigMap value and no run of drops passes it.
- **Check the drain before each repair round.**: A repair round is a plan run with model requests, and the cut at the end of the drain stops only GitHub requests (#4900, #4925). The guard ends the round with the stop, as a gate return does.
- **Log the extension in a sibling line.**: The line `stage review round:` stays one line for each review, so its count and the `verify_rounds` count of the result line stay right. The sibling line `stage review extended:` names the round and the two counts that allowed it.

## Rejected alternatives

- **Ask Jev or another model whether the plan improves.**: #4851 and #4866 plan a model check for the gate returns and the review. A count check needs no model and no network, and it can not fail open.
- **Raise the constant to 3.**: Every plan with an open finding would pay one more round, also with no progress.
- **Log the extension as a field of `stage review round:`.**: It changes a documented line that log queries read, and the round that the extension starts has its own review line.
