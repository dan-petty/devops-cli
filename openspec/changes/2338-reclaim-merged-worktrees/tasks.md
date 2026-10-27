# Tasks

## 1. The current directory and the size in `prune`

- [x] 1.1 Add failing tests to `tests/test_repos_worktrees.py`: `prune --confirm` run from inside a clean merged worktree keeps it, reads no pull request for it and names the current directory, also under `--force`; the same worktree is removed from another directory; a removed and a would-remove item carry `size_bytes`; a missing directory has a null size; the preview and the final line give the total. Verify: `uv run devops ci test tests/test_repos_worktrees.py` fails on the new tests.
- [x] 1.2 In `src/devops_cli/git/worktree_inventory.py`, add `directory_size`, the guard for the current directory to `_decided_by_local_state`, `size_bytes` to `WorktreePruneItem` and `total_bytes` to `WorktreePruneReport`. Update the preview and final messages and the item lines in `src/devops_cli/commands/repos.py`. Verify: `uv run devops ci test tests/test_repos_worktrees.py` passes.

## 2. The reclaim in `add`

- [ ] 2.1 Write the failing tests in `tests/test_repos_worktrees_reclaim.py`, with real repositories and the GitHub fake: a merged worktree is removed with its size and `w-<issue>` is created; the merged worktree of the same issue no longer holds it; a dirty, a locked and an unmerged worktree stay; `--no-reclaim` keeps the merged worktree, reads nothing and refuses the issue it holds; a GitHub error becomes a warning and `reclaim_error` and the worktree is created; the dry run lists the request, makes none and removes nothing; the worktree of the current directory stays. Verify: `uv run devops ci test tests/test_repos_worktrees_reclaim.py` fails.
- [ ] 2.2 In `src/devops_cli/git/worktree_add.py`, add the reclaim before the check for a holder, with `reclaimed` and `reclaim_error` on `WorktreeAddReport`. In `src/devops_cli/commands/repos.py`, add `--reclaim/--no-reclaim`, the removed lines and the warning. Add the messages and the help text. Make the helper of `tests/test_repos_worktrees_add.py` pass `--no-reclaim`, since those tests use a local bare repository as `origin`. Verify: `uv run devops ci test tests/test_repos_worktrees_reclaim.py tests/test_repos_worktrees_add.py tests/test_repos_worktrees.py` passes.
- [ ] 2.3 Run `uv run devops docs generate --sync-readme`. Verify: `uv run devops ci docs` passes and `docs/CLI_REFERENCE.md` lists `--no-reclaim`.

## 3. Documents and the real host

- [ ] 3.1 In `CONTRIBUTING.md`, in the paragraph on starting work, say that `add` first removes the worktrees of merged work, what it keeps, and `--no-reclaim`. Verify: `uv run devops ci docs` passes and `uv run devops ci test tests/test_agents_md_claims.py` passes.
- [ ] 3.2 On the real host, run `add --dry-run` in the main repository and read the plan, which lists the merged worktree that is waiting. In a scratch clone of the real repository, with the real `origin`, make a worktree at the head of merged pull request #2348, then run `add` for a free issue number. Verify: the worktree of the merged pull request is removed with its size, the new worktree is created, and a second run removes nothing.
- [ ] 3.3 Run the full `uv run devops ci --check --no-cache` in the worktree. Verify: every check passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
