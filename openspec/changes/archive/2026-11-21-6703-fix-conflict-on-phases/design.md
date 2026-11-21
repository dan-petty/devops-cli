# Design

## Decisions
- **The phases as fix-checks has them.** `prepare` admits the round (`admit_round`: the bounds and the hard cap), clones, finds the conflicts and the release rule with `git merge-tree`, and checks the caps. A round that ends there gives its report and writes a state that says so. Else the state file and the inputs go to the agent, and the agent's outcome to `publish`.
- **One cleanup path, one record.** The release rule is decided in `prepare` and passed to the agent, so each round that reaches the agent ends in `publish`, which writes the rounds, the files and the result. The agent aborts the rebase and resets the clone to the judged head for each round that does not end `resolved`.
- **The claim before the push.** `publish` checks the admission bounds again with the judged head right before the push, as the other phased steps check the claim.
- **Tier 1 at each stop.** The shared rules make the generated documents and `uv.lock` again at the stop where they conflict, as implement does (owner answer of 2026-11-21).
- **The archive function.** `archive_change` takes the program runner and the commit of the step. implement keeps its documents step, its step labels, the `pre-commit` stage of its commit and the class `plan_defect` around the call.
- **A rebase that git cannot go on with.** The shared loop stops when `--skip` or `--continue` fails and `REBASE_HEAD` stays the same, so a refusal cannot loop. fix-conflict had this guard before; implement and fix-checks get it too.
- **The archive skip of the item only.** A commit that also archives another change is no archive commit of the item: a skip would drop the archive of that change, which the step does not make again. fix-conflict had this rule before; implement and fix-checks get it too.

## Rejected alternatives
- **Keep the push through `OriginGit` from the clone.** Its update of the remote-tracking ref ran the hooks of the clone, which tier 1 can write (#6640 comment).
- **Keep the author check of fix-conflict, which takes any `[bot]` author.** `clone_branch` takes only commits of the App, as implement and fix-checks do, and a second check would be a copy.
- **Move all of `_finish_change` of implement into the shared function.** It sets step labels, commits through the `pre-commit` stage and classifies a failed archive as `plan_defect`; only its archive call fits the shared function.
