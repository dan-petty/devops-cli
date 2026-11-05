# Proposal

## Why

Issue #3392: the implement job stops an item when its staged branch holds a commit by a person. GitHub writes a merge commit with that person as author when the person presses "Update branch". This merge commit changes no file by hand. A routine branch update therefore stops the item. `devops roadmap explain 3318` reports `Its branch has a commit by Daniel Petty, not by devops-cli-service[bot].` The branch of PR #3334 held one App commit, then a person pressed "Update branch".

## What Changes

- A merge commit with two parents is a clean merge when `git merge-tree --write-tree <first-parent> <second-parent>` exits 0 and prints the tree of the commit. The author of a clean merge is not an author of the branch.
- A merge commit with a different tree still counts. It changed a file or resolved a conflict, so its author stops the implement job and refuses `devops repos worktrees add`. The message names the author, as today.
- The rule lives in one module, `src/devops_cli/git/branch_authors.py`. `branch_authors` in `src/devops_cli/roadmap/clone_git.py` and the takeover check in `src/devops_cli/git/worktree_add.py` both call it.
- The stage job reads the same authors when it reconciles a closed item. A staged branch whose only other commit is a clean merge by a person is removed with its draft. That branch holds no person work past `origin/main`, so no work is lost.
- The `git log` read of the authors also prints the parents and the tree of each commit, with the format `%an%x1f%P%x1f%T`. The dry run of `worktrees add` and the dry run of the implement job list that read.
- The change deletes no code.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: a clean merge by a person does not leave the item out.
- `repos-worktrees-add`: a clean merge by a person does not stop the takeover, and a merge that changes a file still does.
- `roadmap-stage`: a closed item loses its staged branch when its other commits are clean merges by a person.

## Impact

- `src/devops_cli/git/branch_authors.py` (new), `src/devops_cli/roadmap/clone_git.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/roadmap/implement.py` (a docstring).
- Tests: `tests/support/roadmap_stage.py`, `tests/roadmap/test_roadmap_implement_selection.py`, `tests/roadmap/test_roadmap_stage_reconcile.py`, `tests/core/test_repos_worktrees_add.py`.
- Documents: `CONTRIBUTING.md` (the paragraph on starting work).
- The change needs git 2.38 or later, which adds `merge-tree --write-tree`. No new package is added.

## Feasibility

- Command output (git 2.55.0, the version in the devcontainer). The merge commit `abe866ce` of PR #3334, in the local object store, has the parents `b85df6347f00a6f79b1aa2f61be98112b897776e` (the App commit) and `df40366d4af38cc554e278c8409b6df6557d2d9b`. Its author is `Daniel Petty`. The command `git merge-tree --write-tree b85df6347f00a6f79b1aa2f61be98112b897776e df40366d4af38cc554e278c8409b6df6557d2d9b` exited 0 and printed `0db60a5a1cdd21790bffcbf010b95ea8d1ddbd4f`. The command `git rev-parse abe866ce^{tree}` printed the same tree.
- Command output (git 2.55.0, a scratch repository in the scratchpad). A clean merge by a person gave the same tree from `merge-tree --write-tree`. A merge with a conflict made `git merge-tree --write-tree` exit 1, and `git merge` printed `CONFLICT (add/add)`.
- Source at `origin/main` (commit `d254410c`). `src/devops_cli/roadmap/clone_git.py` lines 39 to 47 list the author of each commit past the default branch, with no filter for merges. `src/devops_cli/roadmap/implement.py` lines 308 to 311 refuse the first author that is not the App. The issue cites line 305, and the function starts at line 297. `src/devops_cli/git/worktree_add.py` line 341 reads the authors again, and `_check_authors` (lines 228 to 240) refuses the same merge. This second refusal is in the takeover, so the change covers both.
- Limit: the author name of a commit is text that its writer chooses. The rule guards against a mistake and does not guard against a person who forges a name. A check of the GitHub login of each commit needs one request for each commit, which the rule that `add` reads git only (#2337) forbids.

## Existing Tool Considered

- `git merge-tree --write-tree` (git 2.38 or later) builds the merge of two commits without a work tree. Its tree tells whether a merge commit adds more than the merge does. Its exit status tells whether the merge conflicts. This covers the need, so the change builds no comparison of its own.
- `git log --no-merges` was rejected. It also skips a merge that resolved a conflict, so a person's conflict resolution would count as no author. The scratch run above shows that such a merge exists.
- The change deletes no internal code. It replaces the two `git log --format=%an` reads with one shared read.
