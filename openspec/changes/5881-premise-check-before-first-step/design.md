# Design

## Decisions
- **One check before the first step.** `_groups` calls `_check_premise` once, at the first group boundary, after the claim check of that boundary. The check reads every open behavior group of `tasks.md`. A later boundary of the run makes no check, so a guard that an earlier group of the run added is no false premise.
- **The commit of the check.** The check reads `wip_base` at the first boundary. That is the commit that the run starts from after the rebase, less the `wip:` commits of an earlier attempt of the open group. The plan commit of a Staged item is part of it, as before.
- **Only open groups.** A group whose tasks are all ticked passed in an earlier Job. Its guard is on the branch, so a check of it would return a good plan.
- **The spend of a return.** The runner keeps `implement.spend` at a return and leaves `implement.spend_counted` as it is. The Service report reads the new tokens as for every other result, and then clears both keys. The next plan of the item thus starts with no spend, as before.

## Rejected alternatives
- **Check at the default branch tip (`origin/<default>`).** The existing test `TestAFalsePremiseOfABehaviorGroup` puts `_delivery_title` on the staged branch and expects a return. The plan commit is part of the premise of a Staged item, so the check reads the branch.
- **Keep the per-group check and keep the pushed groups at a return.** The late check still costs the tokens and the time of the earlier groups (53 minutes for #3453). A check before the first step costs nothing.
- **The runner clears the spend and writes the tokens in a new key.** A new key needs a reader, a writer and a clear. The report already reads `implement.spend` less `implement.spend_counted`, so a kept spend gives the right count with no new key.
- **A narrow exclusion in `added_guard` for a task that names a test input.** #3453 replaces the prose rule with an `Adds:` line. A check before the first step already stops the loss of work, so no test needs the exclusion.
- **Check the groups that an amendment or a split adds.** A check after a step can come after a group passed, which is the defect of this issue. The amendment judge and the split read the plan for their own rules.
