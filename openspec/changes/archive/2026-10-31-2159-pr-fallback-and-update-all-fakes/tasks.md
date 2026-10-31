# Tasks

## 1. Write failing tests first
- [x] 1.1 Add CLI tests in `tests/commands/test_pr_update.py` for `devops pr edit` REST fallback with title, body, base, and milestone.
- [x] 1.2 Add CLI test for failed milestone PATCH asserting command failure with error message.
- [x] 1.3 Add CLI test checking request plan of `devops pr update --all --dry-run` with and without `--dispatch-ci`.
- [x] 1.4 Add CLI test for `devops pr update --all` over open pull requests verifying oldest-first ordering, skipping drafts, and the empty message.

## 2. Implement PR edit failure message reporting
- [x] 2.1 Update `_fallback_patch_pr` in `src/devops_cli/commands/pr.py` to capture and return error text.
- [x] 2.2 Update `edit_pr` in `src/devops_cli/commands/pr.py` to print failure details with `print_error`.

## 3. Verify tests and quality gates
- [x] 3.1 Verify tests pass with `uv run pytest tests/commands/test_pr_update.py`.
- [x] 3.2 Run `devops ci fail-to-pass --base origin/main`.
- [x] 3.3 Verify static checks: `devops ci lint`, `devops ci format --check`, `devops ci typecheck`.
