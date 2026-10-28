# Tasks

## 1. The rate limiter sends the request, throttle and GraphQL point metrics

- [x] Add failing tests: the requests of a refused and retried gh command, of a GraphQL command and of the GitHub session by resource; the wait of a gh throttle and of a session throttle; the points of a GraphQL answer
  - Verification: `uv run devops ci test tests/test_github_api_metrics.py`
- [x] Add `devops_cli_github_requests_total`, `devops_cli_github_throttle_wait_seconds` and `devops_cli_github_graphql_points_total` to `INSTRUMENTS`, send them from `acquire`, `record_throttle` and `charge_points`, and give `record_throttle` the resource of the request
  - Verification: `uv run devops ci test tests/test_github_api_metrics.py tests/test_github_rate_limiter.py tests/test_github_session.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. The devops-cli dashboard shows the GitHub requests

- [x] Add a failing test: the row "GitHub API" and the queries of its four panels
  - Verification: `uv run devops ci test tests/test_telemetry_instruments.py`
- [x] Add the row and its panels to `devops-cli.json`
  - Verification: `uv run devops ci test tests/test_telemetry_instruments.py tests/test_grafana_dashboards.py tests/test_k8s_monitoring_dashboards.py`

## 3. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 814-github-request-metrics`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

## Workflow follow-up

- Not built: the gauge of the GraphQL points left and the spend by repository of each Service round. They come from the board reads that #2399 removes.
- Not built: the gauge `devops_cli_service_paused_until_seconds`. The Service does not run (#1562), and #1647 and #2399 change why it pauses.
