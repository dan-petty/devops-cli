# Design

## Decisions
- **One seam.** `RunnerUnit` holds the row, the repository, the item, the args, the size, the name, the deadline, the labels, the annotations and the suspension. `runner_job` builds the manifest (the gate check reads it) and `launch` creates it. `build_job` adds `implement-repo` only for the implement row.
- **Due by predicate.** `fix_checks_check(state)` names the failed check of a unit: a shard of `Tests & Coverage` first, a check in the bucket FAIL only, and a class of its name in test, lint, types or plan check. `due_steps` routes it to `fix_checks`; `due_jobs` takes it with #5504.
- **Live unit.** A runner Job holds a pull request only while no round reported it (`job_holds`). The name of an ended Job stays in the record, and it held every delivery pull request before.
- **Ready after a fix.** The live-unit fix also opens the READY route of the watch row to delivery pull requests, which called `mark_ready` with no readiness rule. The row now runs the ready path of the step `fix-checks` (`draft_readiness`, the mode) only on a delivery draft that a fix Job repaired, once for each head, and leaves every other delivery draft to its implement Job, as before.
- **Note 1, owner label.** The launcher does not claim the item: plan mode then writes nothing to GitHub. `claim_labels` stops the step on each `owner/*` label but `owner/service`, in any case, and `fix-conflict` uses it too, so its compare with `owner/Service` is gone.
- **Note 2, which check.** The Job passes `--check`, so the unit name and the work agree. A check that no longer fails gives `skipped`. A `ci_infra` failure gets no unit.
- **Note 3, lease refusal.** When the push fails, the step reads the head again. A moved head gives `skipped` with no record, so no ledger counts a failure and the new head is a new unit. A refusal on an unmoved head stays an error.
- **Note 4, counts.** The implement repair loop no longer writes `fix_checks.*`. Its rounds have their own cap inside the implement Job (`implement.repair_rounds`, 6 in the cluster). Shared counts would put a fix unit at its hard cap of 5 after such a Job, so the fix Jobs would do nothing for the pull requests that the owner wants fixed. The fix unit keeps its caps: 3 soft, 5 hard, 3 heads, one round for each head and check.
- **Order and limit.** `model_slots` lists the Jobs of the Service once and counts the live model Jobs. A fix Job that finds no free place is created with `spec.suspend: true`; the implement and stage rows count it against their place, and the watch row resumes it first. In mode `off` a waiting fix Job holds no place.
- **Size and deadline.** A fix Job takes the large row: it runs the check of a whole pull request again, and the watch row reads no plan. Its deadline is the step limit plus 1800 s; `fix_checks_deadline` refuses an order that breaks request < command < step < unit <= 14400 s.
- **Report and next attempt.** The row reads the log tail of each ended fix Job once and writes the outcome in an annotation. A Job with no result line (exit 75 after SIGTERM, a deadline, a kill) is `none`: it gets the next attempt as `<pr>:<head>:<check>#<n>`, at most `continuations_per_item` more, after 30 minutes doubled up to 2 hours.
- **Mode.** The code default is `plan` (ADR 0021 rule 5); the ConfigMap template sets `on` by the owner direction of 2026-11-16 in #5027.

## Rejected alternatives
- **A due mark in Valkey.** The owner decision of 2026-11-13 removes due marks.
- **A file or Valkey queue of waiting fix units.** The implement and stage rows run in other lanes and read no file of the watch row; a lost file would leave the order wrong. A suspended Job is the queue in the cluster and survives a restart.
- **Delete and create again for a retry.** The delete policy admits the delete of a stage Job only, and the runner Job keeps its name for 24 hours (`ttlSecondsAfterFinished`).
- **Claim the item as the Service.** Plan mode would write labels to GitHub, and the release after the Job would race the Job.
- **Size from the plan.** The watch row has no clone, and a read of `tasks.md` per pull request costs requests for a small gain.
- **The 14400 s cap for every fix Job.** A stuck Job would hold a model place for 4 hours.
