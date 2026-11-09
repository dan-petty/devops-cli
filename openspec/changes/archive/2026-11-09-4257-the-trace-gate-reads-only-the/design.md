# Design

## Decisions

- **Facts of all plan runs**: a reply after a return keeps the claims of the first reply, which the first run supported. The facts are the union of the calls of every plan run of the item. The shared `traces` list is cleared at the start of each item, so every entry belongs to the item.
- **Mark the run with its row**: the shared list holds plan runs and review runs in order, so the order cannot tell them apart. `RunTrace.row` carries the row that `ToolboxClient` already uses for the metrics of the tool calls. A review reads the plan, not the repository for the planner, so its reads must not support a claim of the planner.
- **One constant per row**: `PLAN_ROW` and `REVIEW_ROW` replace the two string literals of `_AGENT_ROWS`.

## Rejected alternatives

- **Remember the length of the shared list before each plan call**: the planner would count slices of a list that the review also writes to, and a test double would have to follow the same call order. A field on the run states the fact once.
- **Combine all runs, review runs too**: a read by the reviewer would make a claim of the planner true. The gate exists to catch a claim that the planner did not check.
- **Refuse the claim and rely on the return**: the return already happened once; the second refusal ends the item.
