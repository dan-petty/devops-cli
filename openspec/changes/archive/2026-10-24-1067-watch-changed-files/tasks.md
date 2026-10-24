# Tasks

## 1. Failing tests first

- [x] 1.1 Write `test_review_path_watch_reviews_only_changed_files` and `test_review_path_watch_skips_deleted_files_and_runs_no_review` in `tests/test_review.py`, and verify failure on current code with `uv run devops ci fail-to-pass --base origin/main`

## 2. Implementation

- [x] 2.1 Update `HELP.options.watch` in `src/devops_cli/lang/en/help.py` and add `no_reviewable_files_changed` in `src/devops_cli/lang/en/messages.py`
- [x] 2.2 Implement `_prepare_watch_content` in `src/devops_cli/ai/review/runner.py` to filter changed paths and construct review pages
- [x] 2.3 Update `path()` in `src/devops_cli/commands/review.py` to use `_prepare_watch_content` in `_on_change` and pass pages to `_execute_current_review`
- [x] 2.4 Verify tests pass locally with `uv run devops ci test tests/test_review.py`

## 3. Documentation and validation

- [x] 3.1 Regenerate CLI documentation with `uv run devops docs generate --sync-readme` and verify with `uv run devops docs check`
- [x] 3.2 Validate OpenSpec artifacts with `uv run devops openspec check`
- [x] 3.3 Run full quality gates with `uv run devops ci`
- [x] 3.4 Archive OpenSpec change with `uv run devops openspec archive 1067-watch-changed-files`
