# Proposal

## Why

Issue #2341: `devops repos worktrees prune` removes worktrees that are in use and refuses worktrees whose work is merged.

- It decides that a worktree is merged when another ref contains the tip. A new worktree has no commit, so its tip is the tip of `main`, and prune removes it. A branch that is pushed to `origin` counts as merged through its own remote ref, so prune removes the worktree of a branch with an open pull request.
- The repository squash-merges. A squash never makes the branch tip an ancestor of `main`, so prune refuses the worktree of a merged branch for ever.
- A failed `git worktree remove` falls back to `shutil.rmtree`, and prune reports "removed". With `--force`, this deletes the directory of a locked worktree.
- A failed `git status` counts as clean.
- The help text says "dry-run by default", but a run without a flag removes worktrees.

## What Changes

- A worktree is removable only when GitHub reports a merged pull request whose head commit is the tip of the worktree. A new worktree, a branch with an open pull request and a worktree that has new commits after the merge have no such pull request, so prune keeps them.
- The check "another ref contains the tip" is deleted, with the `contained` field of `worktrees status` and its table column.
- `prune` removes nothing unless `--confirm` is given. Without it, `prune` reads GitHub and lists what it would remove. `--dry-run` makes no request and prints the requests that the run would make. `--dry-run` and `--confirm` together are refused.
- When `git worktree remove` fails, prune reports the entry as `failed` with the message of git, keeps the directory, and exits 1. The `shutil.rmtree` fallback is deleted.
- When `git status` fails, the dirty count is unknown. `status` shows it as `?` (`null` in JSON), and `prune` refuses the entry.
- A worktree whose directory is gone is removable without a lookup, because removing it drops only the record of git.
- The read-only git commands of the inventory run as local reads, so a dry run shows the real worktrees.
- The change adds the capability `repos-worktrees-prune`. This is observable behavior of a command, so it carries a spec delta.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `repos-worktrees-prune`: which git worktrees `devops repos worktrees prune` removes, refuses and reports as failed, and how its modes behave.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/git/worktree_inventory.py`, `src/devops_cli/github/client.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`.
- `tests/test_repos_worktrees.py`.
- `docs/CLI_REFERENCE.md`, which `devops docs generate --sync-readme` rewrites.

## Feasibility

- Command output at the base commit (`115d1c1c`): in a scratch repository, `prune --dry-run` lists a new worktree and a worktree of a pushed branch as "clean and contained". `prune --force` on a locked worktree prints "removed", deletes the directory, and `git worktree list` still lists the entry as locked. A second run of `prune` on the host removed a new worktree that had no commit.
- GitHub answers: `GET /repos/{owner}/{repo}/commits/{sha}/pulls` returns the merged pull request for the tip of each of four refused worktrees (#2134, #2217, #2140, #2225). Each answer has `merged_at` set and `head.sha` equal to the tip, and the remote branch was deleted. For an unknown SHA, GitHub answers HTTP 422 `No commit found for SHA`. For the merge commit of a squash (`115d1c1c`), GitHub returns pull request #2339 with a `head.sha` that is not `115d1c1c`, so a new worktree at the tip of `origin/main` does not match.
- The documentation of the endpoint says that it returns only open pull requests for a commit that is not on the default branch. The four answers above show the merged pull request, so the documentation is out of date. A change in GitHub toward the documentation gives no match, and prune keeps the worktree. The failure keeps work and never removes it. The tests answer the lookup with the fields of the recorded answers.

## Existing Tool Considered

`git branch --merged`, `git worktree prune` and `git cherry` do not find a squash merge: a squash makes a new commit, and `git cherry` compares patch ids, which differ when the squash joins several commits (several refused worktrees are 33 to 50 commits ahead). The merged pull request of GitHub is the one record of the merge. The change reads it through the existing GitHub session and `GitHubClient`, and builds no tool.

The change deletes `is_tip_contained_in_other_ref`, the `contained` field and column, and the `shutil.rmtree` fallback of `prune_worktrees`.
