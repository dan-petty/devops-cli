# Tasks

## 1. Prune removes only the worktrees of merged pull requests

- [x] Add failing tests: a new worktree, a pushed branch with an open pull request, a worktree with a commit after the merge and a commit that GitHub does not know stay; the tip of a merged pull request is removed; locked, dirty and unreadable worktrees stay without a lookup; a worktree with a missing directory is removed without a lookup
  - Verification: `uv run devops ci test tests/test_repos_worktrees.py`
- [x] Add `GitHubClient.get_commit_pulls` and decide each worktree from local state first and then from the merged pull request of its tip, in `prune_worktrees`
  - Verification: `uv run devops ci test tests/test_repos_worktrees.py tests/test_github_client.py`
- [x] Delete `is_tip_contained_in_other_ref`, the `contained` field and the Contained column of `worktrees status`
  - Verification: `uv run devops ci test tests/test_repos_worktrees.py`

## 2. Prune changes nothing without `--confirm`

- [x] Add failing tests for the preview, for `--dry-run` (no request, the request plan printed), and for `--dry-run` with `--confirm`
  - Verification: `uv run devops ci test tests/test_repos_worktrees.py`
- [x] Add `--confirm` and `plan_prune`, and print the request plan of a dry run with `render_request_plan`
  - Verification: `uv run devops ci test tests/test_repos_worktrees.py tests/test_all_commands_help_dryrun.py`

## 3. Prune reports what git said

- [x] Add failing tests: a forced removal of a locked worktree is `failed` and keeps the directory; a failed `git status` is an unknown dirty count that `status` shows as null and `prune` refuses; a failed read ends the run with nothing removed
  - Verification: `uv run devops ci test tests/test_repos_worktrees.py`
- [x] Report a refused `git worktree remove` as `failed` with the message of git and exit 1, make the dirty count `None` when `git status` fails, and delete the `shutil.rmtree` fallback
  - Verification: `uv run devops ci test tests/test_repos_worktrees.py`

## 4. Documentation and archive

- [x] Regenerate documentation
  - Verification: `uv run devops docs generate --sync-readme`
- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2341-worktrees-prune-merged-pr`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
