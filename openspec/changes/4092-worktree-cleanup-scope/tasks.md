# Tasks

## 1. Keep the add reclaim inside the managed folder and keep ignored files

Kind: behavior

Reads: `src/devops_cli/git/worktree_add.py`, `src/devops_cli/git/worktree_inventory.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/messages.py`, `tests/git/test_repos_worktrees_reclaim.py`. Changes: `src/devops_cli/git/worktree_add.py`, `src/devops_cli/git/worktree_inventory.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/messages.py`, `tests/git/test_repos_worktrees_reclaim_scope.py` (new), `tests/git/test_repos_worktrees_reclaim.py`, `tests/git/conftest.py` (new).

- [x] 1.1 Write `tests/git/test_repos_worktrees_reclaim_scope.py`, move the worktrees of `tests/git/test_repos_worktrees_reclaim.py` under the managed folder, and move the `repo` fixture to `tests/git/conftest.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 1.2 Filter the worktrees in `reclaim_merged_worktrees` by the resolved managed folder, and return each outside worktree as a kept item with the reason `outside the managed folder`, with no GitHub read, also in the dry run
  - Verification: `$ uv run devops ci test tests/git/test_repos_worktrees_reclaim_scope.py`
- [ ] 1.3 Add `count_ignored_paths` and the `include_ignored` option of `inventory_worktrees`, keep a worktree with an ignored path in `_decided_by_local_state` with a reason that gives the count, and set the option only in the reclaim
  - Verification: `$ uv run devops ci test tests/git/test_repos_worktrees_reclaim_scope.py tests/git/test_repos_worktrees.py`
- [ ] 1.4 Add the `kept` list to `ReclaimResult` and `WorktreeAddReport`, and render each kept worktree in the table output of `add` with the texts in `MESSAGES.repos`
  - Verification: `$ uv run devops ci test tests/git/test_repos_worktrees_reclaim.py tests/git/test_repos_worktrees_reclaim_scope.py`

## 2. Say what the reclaim keeps

Kind: documents

Reads: `CONTRIBUTING.md`. Changes: `CONTRIBUTING.md`.

- [ ] 2.1 Update the `devops repos worktrees add` paragraph of `CONTRIBUTING.md`: the reclaim removes only worktrees under `.data/agent/worktrees`, keeps a worktree outside it and a worktree with an ignored file, and names each kept worktree
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: ### Requirement: A run reclaims the worktrees of merged work first `devops repos worktrees add` SHALL remove each worktree that `devops repos worktrees prune --confirm` removes and that is under the agent worktrees directory, SHALL keep a worktree outside it and a worktree under it that holds an ignored file, and SHALL name each worktree that it keeps for these reasons.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
