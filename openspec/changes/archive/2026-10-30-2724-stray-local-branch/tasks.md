# Tasks

## 1. A stray local branch is cleared or named

- [x] 1.1 Add failing tests in `tests/test_repos_worktrees_add.py`: a stray branch at the tip of main (deleted, worktree created, one log line), a stray branch with its own commit (exit 1, branch and commit kept), a stray branch whose commit `origin` holds on another branch (deleted), a stray branch with a pushed staged branch (deleted, takeover), the same with its own commit (exit 1), and the dry-run note
  - Verification: `uv run devops ci test tests/test_repos_worktrees_add.py` fails on the base
- [x] 1.2 Add `_clear_stray_branch` to `git/worktree_add.py` and call it in `_create` and in `_take_over`; add the messages and the dry-run note to `lang/en/messages.py`
  - Verification: `uv run devops ci test tests/test_repos_worktrees_add.py tests/test_roadmap_implement_job.py tests/test_roadmap_stage_plan.py`
- [x] 1.3 Run `uv run ruff check`, `uv run ruff format --check` and `uv run mypy --strict` on the changed files
  - Verification: `uv run devops ci lint`

## 2. Documentation

- [x] 2.1 Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
