# Design

## Decisions

- **One decision per pull request.** `devops pr update <number>` reads the pull request through `gh api`, as before. `merge_conflict` of `github/merge_readiness.py` judges the conflict, the same function that `devops pr check-readiness` and the Service row `pr_conflicts` use. A conflict stops the command before any check read.
- **Required checks from the rules of the base branch.** `read_required_check_names(session, repository, branch)` in `github/check_verdict.py` reads `rules/branches/<branch>` page by page and keeps the contexts of each `required_status_checks` rule. The release pick reads the rules of `main` with it, so one function reads the required checks. `failed_required_checks` in `github/branch_update.py` reads these names and the check runs of the head (`read_check_runs`) through the GitHub session. It returns the sorted names of the required checks in the bucket `fail`, or the reason that a read failed.
- **The update is locked to the head that was judged.** With no `--expected-head-sha`, the command sends the head SHA that it read. If a push changes the head between the read and the update, GitHub refuses the update, so an update never acts on a head whose checks the command did not read.
- **Exit status.** A conflict and a failed read exit 1: the pull request needs an action that the command cannot do. "No required check failed" exits 0: the command did what the rule asks, which is nothing.
- **The rebase steps use plain git.** For a conflict, the command prints `git fetch origin && git rebase origin/<base>` and `git push --force-with-lease`. These are the words of the pre-push hook `branch-current`.
- **The pre-push hook keeps its message.** The hook refuses only a branch that does not hold `origin/main`, and its fix is a rebase. It has no catch-up check, so it never refuses the push that `devops pr update` replaces. The owner said on 2026-11-12 that the first form of #4670 was too complex, and the hook stays a few lines of `sh`.

## Rejected alternatives

- **Delete the whole command (iteration-lane W3).** Owner decision OD1 (a) of 2026-11-11 keeps the single update. Evidence of the decision: with no command, a pull request whose check fails only because of a defect that `main` fixed has no server-side update, and the hooks review found no other path that does not add an escape to the push check.
- **`gh pr checks <number> --required`.** gh finds the required checks through GraphQL (`isRequired`). The GraphQL quota can be short while the REST quota is free, and `fetch_pr_check_verdicts` already falls back to REST for that reason. The REST rules read is already in the release pick.
- **`mergeable_state == "blocked"` as the failed-check signal.** GitHub reports `blocked` also for a missing review and for a pending required check, and the state does not name the check. The command must name the failed check and act only on a failure.
- **Classic branch protection.** The command reads only ruleset rules, as the release pick does. The repository requires its checks through a ruleset. In a repository with only classic protection, the command finds no required check and makes no update, which is the safe side.
