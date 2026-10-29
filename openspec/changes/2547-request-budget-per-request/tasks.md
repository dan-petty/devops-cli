# Tasks

## 1. The budget is checked for each request

- [x] 1.1 Write the tests of the budget in `tests/test_service_limits.py` (a round that waits for the window, the record kept for each request, a closed budget, the session's requests admitted), and verify that they fail on the base
- [x] 1.2 Add `RequestBudget.admit` and `close`, the request gate in `src/devops_cli/github/rate_limiter.py`, and the install of the gate in `ServiceManager`
- [x] 1.3 Update the alert comment in `k8s/monitoring/prometheus-values.yaml`, and verify that `uv run devops ci` passes

## Workflow follow-up

- Pending a person: review the diff.
