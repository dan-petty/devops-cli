# Design

## Decisions
- The batch keys are constants (`CONST_ROADMAP_*_BATCH_KEYS`) next to the intake keys. `_Poll.is_due` already reads `batch_keys`, so no new due logic is needed.
- `scoped_update_wakes_model_lane(delivery, outcome)` holds the wake rule: an edit, or a placement of a critical fix or a P0 item. The consumer calls it after `run_scoped_update`, and enqueues the trigger on the model lane with `enqueue_trigger(..., lane=...)`.
- An edit wakes the model lane whether or not intake placed the issue. The text that refine and retitle read changed in both cases, and one rule is simpler than a second `decided` flag in `JobOutcome`.
- The key that the wake carries is the delivery key. A `refine_due` wake needs no row to declare it: `_Poll.is_due` reads the stamp.
- The Service's own label writes are refused by `refuse_own_write`, so the new `labeled` keys make no loop.

## Rejected alternatives
- Route `edited` to the model lane: the model lane has no intake row, so an edit that needs placing would never be placed.
- A second due stamp for refine: `refine_due` already holds it.
- Wake only the lanes whose rows declare the key: the Service does not know the rows, and the stateless router (#4575) will decide the lane choice later.
