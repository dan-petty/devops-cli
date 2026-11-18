# Design

## Decisions

- **Extend `devops roadmap plan-recheck` with the option `--branches`.**: It reuses the plan reader, the gates, `rewrite_plan`, `validate_change` and the `--confirm` rule, so one command reports the default branch and the open branches.
- **Judge each branch head against the default-branch tree.**: `rewrite_plan` turns a path that the tree lacks into a bare name; the branch tree lacks files that the default branch gained, so the default-branch tree is the tree that the rewrite must see.
- **Rebase in a temporary detached worktree of the clone.**: `checkout_at` leaves the checkout of the caller untouched and removes the worktree, so a stopped run changes nothing locally.
- **Rebase a branch only when the rewrite changes a file.**: The scope comment of 2026-11-11 by dan-petty says the command never rebases an open plan branch only to catch up, and a branch whose plan does not change gets no push.
- **Push once with `--force-with-lease=<branch>:<head>`, on the head that the pass read.**: The rebase rewrites the branch, so a normal push is refused; the lease protects a push that another session made, as `_push` of `src/devops_cli/roadmap/steps/fix_plan.py` does.
- **Let the pre-push hook `branch-current` be the push gate.**: The delivered #4670 holds no `push_branch` function; it holds the hook that fetches `origin/main` and refuses a head that does not hold it, so every push of the pass passes that gate.
- **Dispatch no CI run.**: The push event starts the checks of the pull request, and `devops pr update --dispatch-ci` also updates the branch, which is the catch-up update that the scope forbids.
- **Abort the rebase and push nothing on a conflict.**: A head with conflict markers breaks the plan and the push gate, and a closed pull request discards work that a person can resolve.
- **Add no service row and no schedule.**: The first criterion accepts a command, and a row adds scheduling, runner and budget work beyond this item.
- **Run the tests against the `StageRepo` helper of `tests/support/roadmap_stage.py` and change it not.**: It gives a bare `origin` and a clone in a temporary folder, so the tests run real git offline with no network.

## Rejected alternatives

- **A new `devops roadmap plan-rebase` command.**: It duplicates the command wiring and the validation of `plan-recheck`, which already holds the reader, the gates, the rewrite and `--confirm`.
- **A service row only, with no command option.**: It adds scheduling, runner and budget work beyond this item, and the first criterion accepts a command.
- **All open pull requests.**: `is_plan` in `src/devops_cli/roadmap/plan_check.py` keeps the plans; most open pull requests hold no change folder.
- **Branches with a `plan/` name.**: The repository defines no `plan/` branch name: the stage job names the branch `<type>/<issue>-<slug>` (CONTEXT.md, Staged).
- **Rebase every open plan branch onto the default branch, as the body's step 2 reads alone.**: The scope comment of 2026-11-11 by dan-petty says the command never rebases an open plan branch only to catch up, and a branch whose plan does not change gets no push.
- **In-place checkout of the branch, rewrite then rebase.**: It risks the local state of the caller and can reintroduce old formatting; a temporary worktree keeps the caller's checkout and validates the final tree.
- **The GitHub merge API only, through `gh pr update-branch`.**: The alternatives check of 2026-11-09 records that cli/cli applies no `rewrite_plan`, validates no plan and cannot push a commit with a lease.
- **Push conflict markers, or close the pull request, on a conflict.**: Markers break the plan and the push gate, and closing discards work that a person can resolve.
- **A force push.**: It overwrites a push that another session made; the lease refuses that push instead.
- **A normal push.**: The rebase rewrites the branch, so the remote refuses a push that does not fast-forward.
- **`devops pr update --dispatch-ci` as the CI trigger.**: It updates the branch too, which is the catch-up update the scope forbids, and ADR 0004 records that no `update-prs.yml` workflow exists.
