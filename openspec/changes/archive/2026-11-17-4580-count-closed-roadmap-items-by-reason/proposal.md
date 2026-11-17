# Proposal

## Why

No metric counts the roadmap items that close, by repository and reason, so the pipeline dashboard (#3655) cannot show throughput or the share of items closed as not planned or duplicate. The webhook router already receives each `issues` `closed` delivery, so it can count them with no GitHub request (#4580).

## What Changes

- A new Service counter `devops_cli_service_roadmap_items_closed_total` with the labels `repo` and `reason`, and the reason values `completed`, `not_planned`, `duplicate` and `unknown`.
- The router counts a `closed` delivery of an issue that holds a `priority/*` label, after the duplicate check, so a repeated delivery adds nothing and the closes that the jobs make as the App bot count.
- `WebhookIssue` gains `labels` and `state_reason`, which the router reads from the signed payload.
- The router primes the counter at 0 for each managed repository and each reason when it builds its routes.
- The dashboard `k8s/devops/dashboards/roadmap-service-telemetry.json` charts the counter in the row "Roadmap Service".
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-counters`: The closed-items counter and its panel

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/models/webhooks.py`, `src/devops_cli/server/routes/webhooks.py`
- Dashboards: `k8s/devops/dashboards/roadmap-service-telemetry.json`
- Tests: `tests/server/test_server_service.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/grafana/test_grafana_dashboards.py`

## Feasibility

- The premise holds in the code at the staging commit. `_route` in `src/devops_cli/server/routes/webhooks.py:560` runs the duplicate check and hands the payload to the consumers, and `WebhookIssue` in `src/devops_cli/models/webhooks.py:24` reads no label and no `state_reason`.
- The counter follows `CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES` (`src/devops_cli/config/constants.py:1745`) and the prime follows the `GLOBAL_METRICS.prime_counter` call of `create_webhook_router`.
- The `priority/` prefix is `CONST_ROADMAP_PRIORITY_LABEL_PREFIX` (`src/devops_cli/config/constants.py:4016`).
- The first check is `uv run devops ci test tests/server/test_server_service.py`, which runs the new cases beside the existing ones.
- The second check is `uv run devops ci test tests/telemetry/test_telemetry_instruments.py tests/grafana/test_grafana_dashboards.py`, which checks the series and the panel.
- The third check is `uv run devops openspec check`, which validates the added requirements and their scenarios.

## Existing Tool Considered

`prometheus_client` 0.26.0 (Apache-2.0 AND BSD-2-Clause, maintained, the in-use tool of the alternatives check of 2026-11-13) covers the counter through `GLOBAL_METRICS` (`src/devops_cli/telemetry/metrics.py:103`). It holds no `repo` and `reason` label sets, no bounded reason values and no zero priming for this counter, and this change adds them. No library counts closed issues on its own, because the count needs the delivery that the router receives. The written cost is about 6,000 tokens and about 1 hour.

## Dependencies

None. #3655 reads the series in its pipeline dashboard and no longer blocks this change.
