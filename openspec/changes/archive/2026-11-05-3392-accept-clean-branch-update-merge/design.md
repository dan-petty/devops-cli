# Design

## One rule in one module

`src/devops_cli/git/branch_authors.py` holds the rule. Two callers use it. `branch_authors` in `src/devops_cli/roadmap/clone_git.py` serves the implement job and the stage reconcile. The takeover in `src/devops_cli/git/worktree_add.py` serves `worktrees add`. The module sits in `git/`, because `worktree_add.py` lives there and `clone_git.py` already imports from `devops_cli.git`.

Rejected: two copies of the rule, one in each caller. Today the author read exists in two places (`clone_git.py` lines 39 to 47 and `worktree_add.py` line 341). A second copy would drift.

## One log call with the parents and the tree

The read is `git log --format=%an%x1f%P%x1f%T origin/<default>..origin/<branch>`. The separator `%x1f` is the unit separator. `%P` gives the parents and `%T` gives the tree, so the rule reads each commit once and needs no further read of the commit.

Rejected: `git log --no-merges`, the alternative of the issue. It also skips a merge that resolved a conflict. A person who resolves a conflict would then count as no author. The scratch run in the proposal shows that such a merge exists.

## merge-tree decides

For a commit with exactly two parents, the rule runs `git merge-tree --write-tree <first-parent> <second-parent>` with `local_read=True`. The merge is clean when the command exits 0 and its first line is the tree of the commit. Exit status 1 means a conflict, so the commit keeps its author.

Only two-parent commits are checked, because `merge-tree` merges two commits. An octopus merge by a person keeps its author. Any commit with one parent, and the root commit with none, keeps its author.

Evidence: the merge `abe866ce` of PR #3334 has the tree `0db60a5a1cdd21790bffcbf010b95ea8d1ddbd4f`, and `merge-tree` prints the same tree (proposal, Feasibility).

## The call runs as a local read

The call reads only the object store. It makes no request to `origin`. `local_read=True` lets the call run in a dry run too, as the process runner allows local reads in a dry run (`src/devops_cli/core/process.py`). The `log` read keeps its existing form. In a dry run it returns no text, so the rule finds no merge and calls nothing.

## The stage reconcile follows the rule

`_foreign_commits` in `src/devops_cli/roadmap/stage.py` counts the authors that `branch_authors` returns. A closed item's staged branch whose only other commit is a clean merge by a person is removed with its draft.

Rejected: a second rule for the stage job that keeps such a branch. The purpose of the reconcile is to keep a branch that holds person work. A clean merge holds no person work, because its tree is the tree of its parents. So the stage job and the implement job use one rule. The living spec `roadmap-stage` changes with a MODIFIED delta.

## An empty author list

A branch whose commits past main are all clean merges has an empty author list.

- `worktrees add` keeps its refusal for a branch with no commit. The refusal is `worktrees_add_held_no_commits`.
- The implement job keeps its check. It refuses only a foreign author. It does not refuse an empty list, as today.

Rejected: a new refusal in the implement job for an empty list. The App pushes every staged branch, so a staged branch holds an App commit. The implement job does not check for one today, and this change adds no check.

## The dry run

`worktrees add --dry-run` lists the new `log` call. It cannot list the `merge-tree` calls, because they depend on the commits that the `log` call returns. The implement job's dry-run plan (`src/devops_cli/roadmap/request_plan.py`) lists the same `log` call with the new format.

## Git version

`git merge-tree --write-tree` needs git 2.38 or later. The devcontainer runs git 2.55.0. The tests of this change run the same command, so a runner with an older git fails them. That failure is the check for the runner. This change does not confirm the runner's git version by any other means.
