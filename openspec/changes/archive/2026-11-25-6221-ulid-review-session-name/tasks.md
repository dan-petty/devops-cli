# Tasks

## 1. Behavior

- [x] 1.1 Add failing tests covering `new_session_name()`, ULID format and millisecond order, `ReviewPipelineOrchestrator` default session names, `ReviewSessionStore` and dashboard mixed-format sorting, and `devops review branch` / `devops review pr` session naming
  - Verification: `$ uv run devops ci test tests/ai/test_review_session_store.py tests/commands/test_review_pr_post.py`
- [x] 1.2 Pin `python-ulid` in `pyproject.toml`, map `"python-ulid" = "ulid"` in `[tool.deptry]`, refresh `uv.lock`, and implement `new_session_name()` and `session_sort_key()` across `review/session.py`, `commands/review.py`, `ai/review/pipeline.py`, and `ui/data_providers.py`
  - Verification: `$ uv run devops ci test tests/ai/test_review_session_store.py tests/commands/test_review_pr_post.py tests/ui/test_ui_review_session_discovery.py`
- [x] 1.3 Verify `lockfile` and `deps` gates and run `devops openspec check`
  - Verification: `$ uv run devops ci --check --only lockfile,deps && uv run devops openspec check`

## 2. Documents

- [x] 2.1 Update review session directory wording in `docs/SELF_IMPROVEMENT.md` if required and run `devops ci docs`
  - Verification: `$ uv run devops ci docs`

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
