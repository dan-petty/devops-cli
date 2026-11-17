# Tasks

## 1. Count the closed roadmap items

Reads: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/models/webhooks.py`, `src/devops_cli/config/constants.py`, `tests/server/test_server_service.py`. Changes: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/models/webhooks.py`, `src/devops_cli/config/constants.py`, `k8s/devops/dashboards/roadmap-service-telemetry.json`, `tests/server/test_server_service.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 1.1 Add cases to `tests/server/test_server_service.py`: a close counts by repository and reason, a candidate counts nothing, a close with no reason counts `unknown`, a repeated delivery counts once, a close by the App bot counts, and the counter starts at zero for each repository and reason
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py` fails on the base
- [x] 1.2 Add the `labels` and `state_reason` fields to `WebhookIssue`, the counter constant and the reason values to `src/devops_cli/config/constants.py`, and the count and the zero priming to `src/devops_cli/server/routes/webhooks.py`
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py` passes
- [x] 1.3 Add the panel to the row "Roadmap Service" of `k8s/devops/dashboards/roadmap-service-telemetry.json`, and name the counter in `SERVICE_SERIES` of `tests/telemetry/test_telemetry_instruments.py`
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py tests/grafana/test_grafana_dashboards.py` passes

## Criteria

- Group 1: The router SHALL count an `issues` `closed` delivery of an issue that holds a `priority/*` label, with the labels `repo` and `reason`.
- Group 1: The router MUST NOT count a closed issue that holds no `priority/*` label.
- Group 1: The router SHALL prime the counter at 0 for each managed repository and each reason.
- Group 1: The router MUST count each delivery id at most once in its process.
- Group 1: The router SHALL use `unknown` for a close that GitHub gives no reason for, or another value.
- Group 1: The router SHALL count a close whose `sender.login` is the App bot.
- Group 1: The dashboard SHALL chart the counter by `repo` and `reason` in the row "Roadmap Service".

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
