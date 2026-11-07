# Design

## Decisions

- **Two adapter classes, one in `stage.py` and one in `alternatives.py`.**: Each row writes a different set of artifacts, so a shared type would hold the union of both. `RefineWriter` is tied to `RefinedItem`, `RefineFailure` and `_apply_result`.
- **`plan_stage` and `plan_alternatives` take an optional writer.**: The loop holds the result of each item the moment it is done. A callback adds no thread and no second pass. With no writer the plan stays read-only, so `--plan` makes no write.
- **Stage order: unselected writes, then plan and write each selected item.**: The removals and the rejections of unselected items need no model, so they go before the first plan call. A stop then loses only the unfinished items.
- **A rejection of a selected item goes after its plan and before its publish.**: The flag `staged` of `_reject_plan` is then true only when the plan is ready, and the branch of the rejected plan is deleted before the new push.
- **The moved paths are read for one item, just before its publish.**: The read is git only. It sends no GitHub request, and it sees a commit that landed during the plans of the earlier items.
- **A stop of the Service and rejected credentials end a stage round.**: Both make every later request fail. The round records the failures of the finished items, then raises. Every other error is the failure of one item.
- **Alternatives: write check N before check N+1, and end on a rate limit.**: A kill loses only the check in progress. A rate limit blocks every later write, so the round must not spend model tokens on the other items.

## Rejected alternatives

- **One shared Protocol for both rows.**: `RefineWriter` is tied to its own types, so the shared type would carry the union of what stage and alternatives write.
- **Extend `RefineWriter` to all three rows.**: Stage writes publish, return, rejection and moved paths, and alternatives writes a body block, a record and a comment. `RefineWriter` holds none of these.
- **Keep the five-phase `apply_stage` after all plans.**: A stop loses every finished plan of the round. This is the defect.
- **Plan and write every item, including the unselected ones.**: Removals and rejections need no model, so a plan call for them wastes tokens and time.
- **End the round on every error.**: One error of one item would drop the finished items of the round.
- **End the round on no error.**: A stop or a refused identity would waste the rest of the request window.
- **Retry a rate-limited write until it succeeds.**: A rate limit blocks every later write, so the round cannot finish in the request window.
