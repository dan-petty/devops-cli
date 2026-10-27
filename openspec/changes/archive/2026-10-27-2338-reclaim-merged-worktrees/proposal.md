# Proposal

## Why

Issue #2338: the worktree of a merged pull request stays on disk until a person runs `devops repos worktrees prune --confirm`. Each one holds a full virtual environment: a real worktree on this host is 46,586 files and 1.22 GB. Before the owner's last run of `prune --confirm`, 57 of 125 worktrees were merged. About an hour after that run, one merged worktree was back (`update_uv_and_python`, the head of pull request #2345), so the pile grows again at the rate of the merges.

A merged worktree also blocks the next piece of work. It still has a branch `<type>/<issue>-<slug>`, so `devops repos worktrees add 2344 --type chore --slug again` is refused today with `Issue 2344 is held by the worktree …/update_uv_and_python`, although that pull request is merged.

## What Changes

- `devops repos worktrees add` removes the worktrees of merged work first, before it checks who holds the issue. It removes exactly the worktrees that `prune --confirm` removes: clean, not locked, with a tip that is the head of a merged pull request. `--no-reclaim` skips this step. The output names each removed worktree with its size.
- The reclaim never stops the run. When the pull requests cannot be read, `add` says why once, removes nothing and goes on to create the worktree.
- `prune` and the reclaim keep the worktree that holds the current directory, also under `--force`, and read no pull request for it.
- A removed or removable worktree reports the size of its directory (`size_bytes` in the JSON, a size in the table), and the preview and final lines give the total.
- `add --dry-run` lists the GitHub reads that the reclaim would make, and removes nothing.
- CONTRIBUTING.md says that `add` reclaims merged worktrees.
- This change fits one pull request. It adds requirements to the capabilities `repos-worktrees-add` and `repos-worktrees-prune`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-worktrees-add`: `add` reclaims the worktrees of merged work first, and a failed reclaim does not stop it.
- `repos-worktrees-prune`: the worktree of the current directory stays, and each removable worktree reports its size.

## Impact

- `src/devops_cli/git/worktree_inventory.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- Tests: `tests/test_repos_worktrees.py`, `tests/test_repos_worktrees_reclaim.py` (new) and `tests/test_repos_worktrees_add.py`, whose helper passes `--no-reclaim` because those tests use a local bare repository as `origin`.
- Documents: `CONTRIBUTING.md` and the generated `docs/CLI_REFERENCE.md` and `docs/commands/repos.md`.

## Feasibility

- Command output: `devops repos worktrees prune` on 2026-10-27, after the owner's cleanup, listed 8 worktrees and 1 removable (`update_uv_and_python`, pull request #2345). The whole preview took 4.5 s, including the start of the command, for 4 pull request reads: one `GET /repos/{repo}/commits/{sha}/pulls` for each worktree that local state does not decide.
- Command output: `add 2344 --type chore --slug again --dry-run` on the same host exited 1 with `Issue 2344 is held by the worktree …/update_uv_and_python on branch chore/2344-update-uv-and-python`. A merged worktree holds its issue until it is pruned.
- Command output: walking `update_uv_and_python` with `os.walk` found 46,586 files and 1.22 GB in 0.38 s, so the size of each removable worktree costs little.
- Code: `_decided_by_local_state` in `worktree_inventory.py` guards the main worktree, a forced removal, a lock, a missing directory and the dirty state. It has no rule for the current directory, so `prune --confirm` run inside a clean merged worktree removes the directory the shell is in. Task 1.1 shows this with a failing test.
- The trigger is the choice the issue leaves to this change. Four places were looked at:
  - The end of a `devops pr` command cannot fire: AGENTS.md says that only a person merges, and the merge happens in GitHub after the agent's commands have ended.
  - `devops workspace clean` is a manual command like `prune`, and it removes old files of the data directory.
  - `devops roadmap run` runs jobs against GitHub and its own clones under `data/roadmap`. It does not see the worktrees of a workstation.
  - A throttled side effect of `devops gh` or `devops pr` would remove directories as a hidden effect of an unrelated command.
  - `add` is the first command of every piece of work (CONTRIBUTING.md and SDLC.md), and it needs a merged worktree gone when that worktree holds the issue. It runs often, and a person expects it to change the worktrees.

## Existing Tool Considered

- `git worktree prune` removes only the record of a worktree whose directory is gone, and `git worktree remove` removes one worktree. Neither selects merged work.
- GitHub's setting "delete branch on merge" removes the remote branch and leaves every worktree.
- No open tool removes the worktrees of merged pull requests for several agent tools. `devops repos worktrees prune` already selects them, so the change reuses `prune_worktrees` and builds only the trigger, the guard for the current directory and the size. It deletes no internal code.
