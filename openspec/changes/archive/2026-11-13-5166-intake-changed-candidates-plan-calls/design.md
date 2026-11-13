# Design

## Decisions

1. **The writer of the intake line leaves out a changed candidate.** `_count_candidate` gets the keyword `logged`. The `except RoadmapItemChangedError` branch of `apply_intake` passes `logged=False`, so the counter `devops_cli_roadmap_intake_candidates_total` keeps its `skipped` count and no result line is written. This is the rule that `job-success.md` already gives for an alternatives check whose body a person changed, and for a refine item that another writer changed.
2. **The planner counts its own plan calls.** `_ask_plan` adds 1 to `_plan_calls` of the item in hand before each call to the model, after the check of the time budget. A call that fails counts too, as a run trace did. `_start_item` sets the count to 0. A toolbox client makes one plan run trace for each such call, so the count is the same as before for the Service. A client that keeps no trace now counts its calls.
3. **A kept plan has no count.** `plan` records whether the item starts from a kept plan (`_kept_start`). `note_attempt` then writes `plan_calls=None`, and `StageAttempt.counts` leaves `plan_calls` out of the line. The calls that made the kept plan belong to an earlier attempt, and the plan record does not hold them. A new plan after a refused kept plan still has no count, because the item needed the plan of the earlier attempt too.
4. **The grade needs no change.** `_is_first_pass` in `job_grade_report.py` reads a missing count as no first pass. So a line with no `plan_calls` cannot make a false first pass.

## Rejected alternatives

- **Write `plan_calls=0` for a kept plan.** The two lines in Loki show that 0 reads as a first pass with no plan call, and a staged plan needs at least one call. The issue asks for no field when no count is possible.
- **Keep the plan calls in the plan record.** The record would give a count for a kept plan, but the record format and its key change, and every kept file of the Service becomes a miss. The issue asks only for a true line, and a kept plan is rare (two lines in 7 days).
- **Log the changed intake candidate as a success.** It is not a placement by intake. `success=true` would make the grade too high, as `success=false` made it too low.
- **Remove the `skipped` count of the changed candidate from the counter.** The issue asks to keep `devops_cli_roadmap_intake_candidates_total` as it is, and the telemetry test of #4042 holds that count.
