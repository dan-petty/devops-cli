# Design

## Decisions

- **The run ends at the draft.** After `_pull_request`, `_end_drafted` writes the marks that `_ready` wrote (the last commit, the pull request, the spend, the trace, the repair rounds, and no base and no phase marks), with `implement.result` equal to `drafted`, and sets Status In Review, as #3702 asks for the end of `publish`. The comment on the item names the draft and the spend.
- **The grade gets a new baseline.** The intended result of `implement` is `drafted`. The owner wants the grade to follow the forge outcome of the pull request. A result line that waits for the ready mark or the merge needs a second writer of the implement line and a mark for each pending attempt, and an attempt whose draft never moves would write no line at all. The `fix_checks` lines and the verdicts of the delivery pull requests already measure what follows the draft, so the implement line measures only what the Job does. `docs/roadmap/job-success.md` says that the ratio starts again at the first version with `drafted`.
- **One predicate for the ready path.** `takes_ready_path` of `fix_checks.py` holds the rule for the watch row and for the step: `fix_checks.result` equal to `repaired`, or `implement.result` equal to `drafted`. The draft of a stopped Job stays a draft, as before.
- **The step keeps no work in progress.** The step records the commit where it started (`start`) and resets to it when it does not end done. The exit checks judge everything since `start`. The rename restore of a stray file (#3488) moves from `implement_wip.py` into `implement_step.py`, because the exit checks still use it.
- **The scoped-check repair stays.** `_fix` serves `_scoped_rounds`, the repair of a failed scoped check before the push, which needs no GitHub call. Only its caller in the watch loop (`_repair_after_push`) goes. #6527 decides the scoped repair of the stock `Coder`.
- **The checkpoints stay.** A checkpoint pushes each group that passed between the steps. Part C of #3702 removes all pushes from the agent phase.
- **The stall keeps its value.** `deadline_stall_seconds` stays 4200: the change removes the watch, and the longest silent wait is now a command of 1800 s. #5029 owns a lower value.

## Check classes that lose the repair of the Job

Before, the Job repaired a failed check of any class whose log named a path of the repair scope (`_repair_after_push`). The watch row starts a fix-checks Job only when the name of the failed check gives a class of `FIX_CHECK_CLASSES`: `test`, `lint`, `types` or `plan_defect` (`fix_checks_check` of `steps/watch.py`, from `_CHECK_NAMES` of `failure.py`). A failed check whose name gives `ci_infra` loses the repair: a name with `image`, `duration`, `devcontainer`, `build`, `setup` or `install`, and a name that no rule matches, such as `Deploy Preview` or `Semantic PR title`. The row comments on such a check and waits. Before, the Job ran a fix step for such a check when its log named a path of the plan.

## Rejected alternatives

- **Write the implement line at the ready mark or the merge.** Rejected: it adds a writer of the result line and a pending mark, and it loses each attempt whose draft never moves (see Decisions).
- **Keep the `wip:` commits and drop only their push.** Rejected: the owner decision names `implement_wip.py`, and in the split of #3702 the agent phase hands one patch to `publish`, so a commit that no push sends keeps nothing.
- **Delete `_fix` with the watch loop.** Rejected: it removes the repair of a failed scoped check before the push, which no criterion asks for.
