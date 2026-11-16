# Design

## Decisions
- **Rules before the model (ADR 0020).** The rules take the facts that a program reads, in a fixed order: issue changed (closed item, changed text, merged work on the change folder), then merge conflict, then failed checks, then a wait for checks, then open findings, threads and an incomplete change. The model reads the diff, the plan and the issue only when no rule applies. A green, complete pull request is the only case that costs a model call.
- **The issue edit is a hash, not a time.** `stage.text_hash` is the hash of the text that the plan came from. The update time of an issue moves at each label and each record write, so a time compare would mark each item as changed.
- **Related work is the merged pull requests since the merge base.** One GraphQL request walks the history of the base branch back to the merge base and reads the files of each associated pull request. Only a change to the change folder of the item gives issue changed; other shared files go to the model as context. The plan pull request of the item is no related work.
- **Due fix by kind.** A plan always leaves `fix-plan`: the label `verdict/fix-plan` starts that row, and its revision is a commit on the latest base, so it settles a conflict too. A delivery leaves `fix-conflict` or `fix-checks`, or no step when only a person or a later step can fix it.
- **Writes need `--confirm` and the mode `on`.** The mode `off` is the stop switch of each caller, `plan` gives the verdict with no write, so a week of result lines shows the verdicts before any write. The launcher of #5027 passes `--confirm` only in the mode `on`.
- **Own labels only.** The step replaces the verdict labels that only it writes. `verdict/fix-plan` stays, because the stage job, `plan_drift` and `fix-plan` own its claim.
- **Discard reuses the return paths.** The step closes the pull request, deletes the branch with a lease on the judged head (`OriginGit.push`), and returns the item with `apply_return`, which clears `STAGE_REMOVAL_KEYS` or the keys of the delivery that the implement job clears at a return. A closed plan with its record cleared is no rejection of a person, so the stage job plans the item again after refine. A delivery on the branch of its plan pull request is left for a person: a delete would lose the plan.
- **Cap of 3 verdicts for each pull request** in the record of the item (`review.pull`, `review.rounds`), as the owner asked ("Repeat 2 or 3 times"). At the cap the step comments once and leaves the pull request for a person.
- **Idempotent.** `review.key` is the pull request, the head and the hash of the issue text, so the same head gets no second verdict and the next head or an issue edit gets one.

## Rejected alternatives
- **Use `Item.updated_at` against the head time.** Rejected: the record of the item lives in its body (ADR 0016 D5), so each job write moves the time.
- **A merged pull request that shares any file gives issue changed.** Rejected: shared files such as `docs/CLI_REFERENCE.md` and `settings.py` change in most merges, so most pull requests would get issue changed.
- **Close a plan and let the stage job read it as a rejection.** Rejected: `closed_plans` holds the item until its text changes (`hold_reason`), so the plan would never be made again.
- **Discard after the cap (owner comment of 2026-11-16).** Rejected for now: the brief of the item leaves the pull request for a person after the cap, and a discard deletes work; a person decides after the plan-mode week.
- **The task `analysis` or `fix_checks` for the model.** Rejected: a job reads its own task (#5903), and a new job starts on DeepSeek (owner rule of 2026-11-16).
