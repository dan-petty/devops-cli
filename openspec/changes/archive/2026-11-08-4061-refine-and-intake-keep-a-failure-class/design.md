# Design

## Decisions

- **One table, reused.** The wait of a failure comes from `retry_after`, which the stage job also calls. Refine and intake add no table and no setting. A person who wants another wait changes `RETRY_AFTER`.
- **Refine writes the class where the failure is recorded.** `RefineFailure` gets `failure_class` from `failure_class_of(exc)` when it is made. `_record_failure` is the one writer. For a failure that the item caused, the three keys join the marks of the failed body hash in one write. For another failure, one marks write holds the three keys.
- **The second failure on the same body clears the three keys.** The item then waits on a body edit (`refine.next_step` is `edit`), and a wait of 6 hours would only repeat that wait. Without the clear, a person's edit would meet a stale wait.
- **A body edit ends the wait after a failure that the text caused.** The record holds `refine.failed_body_hash` for such a failure. When the body hash differs, the selection ignores the wait. A failure that the text did not cause has no body hash, and its wait holds: an edit does not change a timeout.
- **A placeholder failure keeps its rule of no record (#3478).** The reply is random, and the next round may give a good one. This keeps the contract and its tests.
- **A time that is no time holds the item for no time.** This is the rule of the stage job (`_failed_lately`). The same applies to a missing or unknown class: `retry_after` returns the wait of `ci_infra`.
- **The wait shows as the step `retry`.** `WaitingItem` with the step `retry` and a detail that holds the time. `NextStep` is what the record stores, so no member is added. The text of `refine_left_waits["retry"]` changes so that it reads right for a job failure and for a wait on a failed model call.
- **Intake drops the candidate before it asks the model.** `plan_intake` filters the held numbers out of the subjects before `_queue`. The numbers go to `IntakePlan.held`. `IntakeRecord.after` keeps the `waiting` and `failed` entries of a held candidate, so the count is not lost, and it keeps the entries of the candidates the round left. It drops the entries of a number that is no candidate any more.
- **The entry is written after the apply.** `IntakeRecord.settled(plan, applied, now)` takes the record that `after` or `merged` wrote, removes the entries of the decided candidates, and adds one for each failed placement with count plus 1. `_apply_round` writes it before it raises. A crash between the two writes loses at most the count of one round.
- **`Failed` stores the enum `FailureClass`.** Intake records one class today (`ci_infra`, from `GitHubOperationError`), and the record file is written by the same image that reads it.
- **A candidate with no number has no entry.** A new candidate never filed (`intake_candidate`, discovery) has no number and no record; that path keeps no `IntakeRecord`.
- **A webhook update honors the wait.** A scoped update of a held candidate decides nothing. The wait is for a failed write, not for the text of the candidate, so an edit of the issue does not end it.

## Rejected alternatives

- **Write the keys in `_failure_marks`, as the issue says.** That function gets a `JobFailure`, which has no exception and no class (see Feasibility). Rejected: it would need a second path to carry the class to it.
- **Mark the item for an intake failure.** The issue is a candidate, not an item, and the issue text says the item record gets no mark. Rejected.
- **Record the placeholder failure with class `parser`.** It would change the rule of #3478 and its tests, and it would hold back a reply that the next try may fix. Rejected.
- **Store the time of the next try.** The record would go stale when the table changes. Rejected: the sum of two facts is cheap to compute (the decision of #4060).
- **Add a `RETRY_AFTER` entry for `timeout`.** A model timeout is class `provider` (`AIClientError`). The class `timeout` is in no table, and an entry would be dead data (the decision of #4060).
