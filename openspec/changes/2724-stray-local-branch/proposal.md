# Proposal

## Why

Issue #2724. The stage job, the implement job and `devops repos worktrees add` make the branch `<type>/<issue>-<slug>` with `git worktree add -b <branch>`. When the clone already holds a local branch of that name, git refuses.

```
fatal: a branch named 'fix/2656-x' already exists
```

The jobs delete their worktree and their local branch when they end. A stray local branch stays only when the process dies between the branch creation and that cleanup, for example when the Service pod is killed. The clone of the Service is on a persistent volume, so the branch stays. No later round removes it, so every later round fails for that item with git's message.

## What Changes

- `add_worktree` clears a stray local branch of the name it is about to create. A stray branch is a local branch of that name that no worktree uses. The check runs after the fetch and before `git worktree add`, in the create path and in the take-over path. Stage, implement and `devops repos worktrees add` all call `add_worktree`, so they share the one change.
- The branch is deleted when every commit of it is also in `origin/main` or in a remote-tracking ref of `origin`. The run logs one line that names the branch and its commit.
- The branch is kept when it has a commit that `origin` does not hold. The run then stops with an error that names the branch and the number of commits. The job leaves the item out and the commits stay.
- A dry run lists no branch deletion, and its note says that the real run can delete a stray branch.
- A consumer observes the error and the behavior of the command, so the change carries one spec delta: a new requirement in `repos-worktrees-add`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-worktrees-add`: two added requirements, `A stray local branch that origin holds is cleared` and `A stray local branch with a commit that origin lacks is kept and named`. No existing requirement changes. The scenario "A local branch with no worktree" stays true, because it uses a branch name that differs from the new branch.

## Impact

- `src/devops_cli/git/worktree_add.py`, `src/devops_cli/lang/en/messages.py`.
- `tests/test_repos_worktrees_add.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The fault is real. On 2026-10-30, with git 2.55.0, in a scratch repository (`.data/agent/scratch/repro`): `git branch fix/2656-x`, then `git worktree add --no-track -b fix/2656-x ../wt origin/main` exits 255 with `fatal: a branch named 'fix/2656-x' already exists`. The take-over command `git worktree add --track -b fix/2656-x ../wt2 origin/fix/2656-x` fails the same way when a local branch of the name exists.
- The test for unpushed commits is possible with plain git. `git rev-list --count <branch> --not origin/main --remotes=origin` prints 0 for a branch at the tip of `origin/main`, 1 for a branch with one commit of its own, and 0 again after the branch is pushed. `--remotes=origin` matches every ref `refs/remotes/origin/*`. The take-over path fetches `refs/remotes/origin/<branch>` first, so the same command covers it.
- The jobs call `add_worktree` before their `try` block. When it raises, no cleanup runs and the stray commits stay untouched.
- On the base, the new tests fail: the run exits 1 with git's message and the branch stays.

## Existing Tool Considered

git covers the need: `for-each-ref` reads the branch, `rev-list --not` finds the commits that `origin` lacks, and `branch -D` deletes. Nothing new is built, and no dependency is added. The code is one helper of about 30 lines in `worktree_add.py`. It replaces no existing code.
