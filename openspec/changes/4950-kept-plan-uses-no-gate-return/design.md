# Design

## Decisions

- **Gate the kept plan in `_gated`, before the return loop.** The kept plan is no reply of a plan run, so it does not go into `_returned`. `_gated` settles it, and on a refusal it logs the `stage reply refused` line, adds the reply and its problem to the refused replies, and asks the planner. `_returned` then counts only replies of the model.
- **The new first reply gets the kept plan and its problem.** The request is the same as the request of a return (`previous` and `problem`), so the planner can keep what is still true and correct what moved. `_Refused.returned` builds it for both callers.
- **The drain guard stays.** `raise_if_service_stops` runs before the new first reply, as before each return (#4900), so no new plan run starts while the Service drains.
- **The refused file keeps the kept plan.** A failed item writes the kept plan and its problem first, then the refused replies of the model, as before.

## Rejected alternatives

- **Start `returns` at -1 for a kept plan.** It gives the same count, but the loop and its log line then hold a value that is not a count of returns.
- **Ask the planner from the plain request, without the kept plan.** The kept plan and its problem show the planner what moved, and a return gives the same input today, so a plain request would drop useful input.
- **Raise the default of `roadmap.stage.gate_returns`.** It gives every item one more run and does not remove the cause; the ceiling of 3 (#4900) also refuses it.
