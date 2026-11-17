# Proposal: #3941

## Why

The row `metrics` of the roadmap Service sends too many GitHub requests. It runs `collect_project_metrics_report` with `GhCliClient.api`, which has no ETag cache and counts every call. It also sends a second paginated listing for open issues after the roadmap store has already read all issues. Closes #3941.

## What Changes

- `get_ci_workflow_metrics` and `get_milestone_metrics` take an optional `session: GitHubSession | None = None` argument and query GitHub through `session.rest` with conditional requests.
- `collect_project_metrics_report` accepts `session: GitHubSession | None = None`, sharing one session across workflow run and milestone collection.
- `get_label_taxonomy_metrics` takes `store: RoadmapStore` and derives taxonomy label counts from open Items that the store already holds, removing the redundant `repos/<repo>/issues?state=open` request.
- `METRICS_ROW_GITHUB_REQUEST_BUDGET` in `src/devops_cli/github/metrics.py` drops from 5 to 4 because the open issues listing is removed.
- Tests verify that no open issues listing request is made and that workflow runs and milestones use the session.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-metrics-dashboard`: Derives taxonomy from store-held open Items and queries workflow runs and milestones through the GitHub session.

## Impact

- `src/devops_cli/github/metrics.py`: `get_ci_workflow_metrics`, `get_milestone_metrics`, `get_label_taxonomy_metrics`, `collect_project_metrics_report`, `METRICS_ROW_GITHUB_REQUEST_BUDGET`.
- `tests/github/test_github_metrics.py`, `tests/github/test_github_metrics_request_budget.py`.

## Feasibility

- `collect_project_metrics_report` receives `store: RoadmapStore`. The store already reads every issue via `store.items()` for `get_item_metrics`.
- `GitHubSession` is available via `get_github_session()` and supports conditional GET requests via `session.rest("GET", ...)`.
- Offline tests verify that `devops_cli_github_requests_total` under `row="metrics"` drops by 1 request per round.

## Existing Tool Considered

`GitHubSession` with ETags covers the need for conditional requests. It is existing project code and requires no external dependency.
