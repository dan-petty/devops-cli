# Design

## Decisions

- **One hook in the configuration, no module.** The hook is a few lines of `sh` in `.pre-commit-config.yaml`, with `entry: sh -c` and the script as its one argument. It needs only git and `timeout`. The runner image holds `sh` (`RUNNER_TOOLS`), and the hook does not get past its first line in the Job.
- **Only a push of a branch is checked.** The hook passes unless `PRE_COMMIT_REMOTE_BRANCH` starts with `refs/heads/`. A tag push and a run of the stage with `--from-ref` and `--to-ref` thus pass. The implement Job runs the stage that way and rebases in code before each push, so a move of `main` during its checks is no failure of the model.
- **Fetch `main` of `origin`, not of the pushed remote.** The rule is about `origin/main`. The hook reads `FETCH_HEAD`, which is a ref of each worktree, so a parallel fetch in another worktree does not change it.
- **20 s for the fetch.** Nothing around the hook has a limit, and a fetch of `main` takes about 1 s. A fetch that fails or runs out of time refuses the push with its own message, because the hook cannot tell whether the branch holds `main`.
- **`fail_fast: true`, first in the stage.** A refused push does not run lint and format.
- **The Job pushes nothing after a rebase conflict.** A head that does not hold `main` breaks the rule. The next Job gets the conflict files and starts from the branch on `origin`.

## Rejected alternatives

- **The first build of #4879**: a module `src/devops_cli/git/push_gate.py`, the commands `devops branches check-push` and `devops branches push`, a check of catch-up-only pushes by patch-id, an ast-grep rule over the push sites, a counter and JSON fixtures. The owner said on 2026-11-12 that it is a complicated alternative to `check-merge-conflict`. The rule needs only the ancestor check.
- **`git merge-tree` for the conflict files**: a branch that holds `main` cannot conflict with it, so the ancestor check is enough. `git rebase` names the conflict files when the author fixes the branch.
- **A refusal of a catch-up-only push**: #4674 deletes `devops pr update`, the main source of these pushes. The docs rule "No Catch-Up Updates" stays.
- **A stop at once when a checkpoint meets a conflict**: it saves model tokens, but it adds a new stop path. The final rebase stops the item with the same conflict.
- **A second rebase in `_push` after the scoped checks**: the Job would push a head that its checks did not see. The rebase at the start of `_push` stays.
- **The ruleset setting "require branches to be up to date"**: it acts at the merge and starts a catch-up run for each move of `main`. The owner keeps it off (ADR 0014).
