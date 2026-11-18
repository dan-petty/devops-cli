# Tasks

## 1. Behavior

- [x] 1.1 Write tests for author checks in `post()` and `post_pr_review_comment()`
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_comment.py tests/commands/test_review_pr_post.py`
- [x] 1.2 Implement author filtering in `src/devops_cli/roadmap/steps/comment.py`
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_comment.py`
- [x] 1.3 Implement author filtering in `src/devops_cli/ai/review/runner.py`
  - Verification: `$ uv run pytest tests/commands/test_review_pr_post.py`

## 2. Verification

- [x] 2.1 Verify fail-to-pass and all quality checks
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
