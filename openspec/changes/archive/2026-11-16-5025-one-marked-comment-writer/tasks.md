# Tasks

## 1. Behavior

- [x] 1.1 Write test for shared marked-comment writer
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_comment.py`
- [x] 1.2 Implement `src/devops_cli/roadmap/steps/comment.py`
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_comment.py`
- [x] 1.3 Add `comment_on_issue` to `GitHubClient` in `src/devops_cli/github/client.py`
  - Verification: `$ uv run pytest tests/github/test_github_client.py`
- [x] 1.4 Migrate comment sites in `src/devops_cli/roadmap/` to `steps/comment.py`
  - Verification: `$ uv run pytest tests/roadmap/`
- [x] 1.5 Add structural test against direct callers of `comment_on_issue` or `comment_on_pull`
  - Verification: `$ uv run pytest tests/structural/test_roadmap_comment_callers.py`
- [x] 1.6 Add implement stop-replay write stops test
  - Verification: `$ uv run pytest tests/roadmap/implement/test_roadmap_implement_write_stops.py`

## 2. Documents

- [x] 2.1 Update `openspec/specs/roadmap-job-comments/spec.md`
  - Verification: `$ uv run devops ci docs`
