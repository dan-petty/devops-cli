# Tasks

## 1. Test session-based reads and store-derived taxonomy

- [x] 1.1 Add unit tests for session-based `get_ci_workflow_metrics` and `get_milestone_metrics` and store-based `get_label_taxonomy_metrics`.
  Verification: `uv run pytest tests/github/test_github_metrics.py -k "test_get_ci_workflow_metrics or test_get_milestone_metrics or test_get_label_taxonomy_metrics"`
- [x] 1.2 Update `tests/github/test_github_metrics_request_budget.py` for the reduced budget of 4 requests.
  Verification: `uv run pytest tests/github/test_github_metrics_request_budget.py`

## 2. Implement session reads and store-derived taxonomy

- [x] 2.1 Update `get_ci_workflow_metrics` and `get_milestone_metrics` in `src/devops_cli/github/metrics.py` to accept `session: GitHubSession | None = None` and call `session.rest`.
  Verification: `uv run pytest tests/github/test_github_metrics.py -k "workflow or milestone"`
- [x] 2.2 Update `get_label_taxonomy_metrics` in `src/devops_cli/github/metrics.py` to accept `store: RoadmapStore` and count labels of open items.
  Verification: `uv run pytest tests/github/test_github_metrics.py -k taxonomy`
- [x] 2.3 Update `collect_project_metrics_report` in `src/devops_cli/github/metrics.py` to pass `session` and pass `roadmap` to `get_label_taxonomy_metrics`, and update `METRICS_ROW_GITHUB_REQUEST_BUDGET` to 4.
  Verification: `uv run pytest tests/github/test_github_metrics.py tests/github/test_github_metrics_request_budget.py`
- [x] 2.4 Verify all checks and tests pass with `devops ci`.
  Verification: `uv run devops ci --check --only lint,format,typecheck`
