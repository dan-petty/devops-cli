# Design

## Decisions
- **The phases as fix-checks has them.** `prepare` admits the round (`admit_round`: the bounds and the hard cap), clones, finds the conflicts and the release rule with `git merge-tree`, and checks the caps. A round that ends there gives its report and writes a state that says so. Else the state file and the inputs go to the agent, and the agent's outcome to `publish`.
- **One cleanup path, one count.** `prepare` adds one to the rounds of the record when it gives the round to the agent, so a round counts also when the agent phase writes no outcome or its container ends. `publish` writes the result, a refusal too, and adds no round; its admission takes no cap. The agent aborts the rebase and resets the clone to the judged head for each round that does not end `resolved`.
- **The output of tier 1 in the stop.** A failed program of tier 1 puts its exit status and the last lines of its output into the reason, as implement does (`implement_stop_program_failed`, `output_tail`). The round masks the reason; no log holds the output.
- **A plan needs no App.** Without `--confirm`, `clone_branch` makes no check of the authors, so a host with no `service.github_app.slug` gets the plan, as on `main`.
- **The claim before the push.** `publish` checks the admission bounds again with the judged head right before the push, as the other phased steps check the claim.
- **Tier 1 at each stop.** The shared rules make the generated documents and `uv.lock` again at the stop where they conflict, as implement does (owner answer of 2026-11-21).
- **The archive function.** `archive_change` takes the program runner and the commit of the step. implement keeps its documents step, its step labels, the `pre-commit` stage of its commit and the class `plan_defect` around the call.
- **A rebase that git cannot go on with.** The shared loop stops when `--skip` or `--continue` fails and `REBASE_HEAD` stays the same, so a refusal cannot loop. fix-conflict had this guard before; implement and fix-checks get it too.
- **The archive skip of the item only.** A commit that also archives another change is no archive commit of the item: a skip would drop the archive of that change, which the step does not make again. fix-conflict had this rule before; implement and fix-checks get it too.

## Rejected alternatives
- **Keep the push through `OriginGit` from the clone.** Its update of the remote-tracking ref ran the hooks of the clone, which tier 1 can write (#6640 comment).
- **Keep the author check of fix-conflict, which takes any `[bot]` author.** `clone_branch` takes only commits of the App, as implement and fix-checks do, and a second check would be a copy.
- **Move all of `_finish_change` of implement into the shared function.** It sets step labels, commits through the `pre-commit` stage and classifies a failed archive as `plan_defect`; only its archive call fits the shared function.
