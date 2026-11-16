# Design

## Decisions
- **The rules run on each call; the key saves only the model.** `review.source` records whether the last verdict came from a rule or from the model. A head and issue text whose model verdict is recorded get no second model call. A rule verdict that the record and the label hold writes nothing; a rule verdict that differs is a new verdict and counts a round.
- **A discard of the model alone does not act.** Issue text can steer the model, and a discard deletes work. The label and the comment let a person decide. No rule gives a discard yet; the deterministic discard after the cap is a decision of the owner on #6011, and it uses the ordered path.
- **The ordered discard.** Mark the start, delete the branch with the lease, close, return. A delete that fails leaves the pull request open, so the next call tries again. After the delete GitHub closes the pull request, so a call on a closed pull request with the mark of its head ends the discard: the delete runs only for a branch that is still there, and the return clears the mark. A closed pull request with no mark of the step is skipped as before, so the close of a person goes to the stage job and the implement job as before.
- **The ready hold is in the pure rule.** `ready_held(labels)` in `steps/watch.py` holds READY for any verdict label but `verdict/mergeable`; the watch row passes the labels that both of its read paths already get from GitHub.
- **A person's ready mark stays.** The step goes back to draft only when the last `ReadyForReviewEvent` came from a bot, or, with no event, when a bot opened the pull request.
- **The infrastructure wait is timed per head**, from the first wait that a write recorded, so the limit does not depend on how often a trigger calls the step.
- **One Issue changed per issue text.** `review.text` keeps the text hash that an Issue changed verdict answered; `stage.text_hash` stays the text of the plan.

## Rejected alternatives
- **Skip the whole call on a recorded key (the first version).** Rejected: a new conflict, thread, label or closed item on the same head is never seen (item 1 of #6024).
- **Close first, then delete (the first version).** Rejected: a failed delete leaves a closed pull request that the guard skips, and the item never returns.
- **Read the labels again in the watch row before each ready mark.** Rejected: one more request for each pull request; both read paths already return the labels.
- **Count the waits on CI infrastructure.** Rejected: the count depends on the cadence of the trigger of #6011; a time limit does not.
