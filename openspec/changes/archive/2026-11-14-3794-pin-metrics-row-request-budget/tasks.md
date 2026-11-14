# Tasks

## 1. Pin the metrics-row request budget (test-only change)

- [x] 1.1 Add `METRICS_ROW_GITHUB_REQUEST_BUDGET` to `src/devops_cli/github/metrics.py`.
  Verification: `uv run python -c "from devops_cli.github.metrics import METRICS_ROW_GITHUB_REQUEST_BUDGET; assert METRICS_ROW_GITHUB_REQUEST_BUDGET == 5"`
- [x] 1.2 Add `tests/github/test_github_metrics_request_budget.py`, which counts the samples of one round with one page of each listing.
  Verification: `uv run pytest tests/github/test_github_metrics_request_budget.py`
- [x] 1.3 Cover the second page of the every-issue listing, which sends one sample over the budget and fails with the count and the budget.
  Verification: `uv run pytest tests/github/test_github_metrics_request_budget.py -k more_page`
- [x] 1.4 Run the metrics tests and the quality gate.
  Verification: `uv run devops ci test tests/github/test_github_metrics.py tests/github/test_github_api_metrics.py tests/github/test_github_metrics_request_budget.py && uv run devops ci --check --only lint,format,typecheck`
