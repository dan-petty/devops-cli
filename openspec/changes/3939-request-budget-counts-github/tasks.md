# Tasks

## 1. The budget counts what GitHub counts (behavior)

- [x] 1.1 Add failing tests: a 304 answer leaves the budget, a 200 answer and a request with no answer stay, and a refund reaches the window, the file and the cost of a round
  - Verification: `uv run devops ci test tests/github/test_service_limits.py`
- [x] 1.2 Add `set_request_gate(gate, refund)` and the call in `count_request`, `RequestBudget.refund`, and the hook in `ServiceManager.start`
  - Verification: `uv run devops ci test tests/github/test_service_limits.py tests/github/test_github_api_metrics.py`

## 2. The alert follows the budget (manifests)

- [x] 2.1 Sum the requests with `status!="304"` in `RoadmapServiceGitHubRequestsHigh`, add the fixture of 480 answers with 304, and update the expected expression
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## 3. The documents state what the budget counts (documents)

- [x] 3.1 Update the metric description, the setting description and `k8s/README.md`, and regenerate the documents
  - Verification: `uv run devops ci docs`

## 4. Archive

- [x] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 3939-request-budget-counts-github`
- Pending a person: after the merge and the rollout, run `sum(increase(devops_cli_github_requests_total{job="roadmap-service", status!="304"}[1h]))` over 24 hours and compare it with 1,800 to 1,970 for all statuses before.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

## Workflow follow-up

- The sources of counted requests have follow-ups with the numbers of 2026-11-07: the row `metrics` in #3941, the row `other` in #3942, and the row `refine` in #3866.
