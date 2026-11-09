# Tasks

## 1. Alert on the daily spend of Claude and of the hosted models

Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/research_tests.yaml`, `src/devops_cli/telemetry/instruments.py`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/ai_spend_tests.yaml`.

- [x] 1.1 Write the tests of the group `ai-spend`: the rule set, the thresholds and selectors, the README rows and the promtool fixture with the series that fire and the series that do not
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] 1.2 Add the group `ai-spend` with `ClaudeSpendDailyHigh` and `HostedSpendDailyHigh` to `k8s/monitoring/prometheus-values.yaml`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## 2. List the alerts in the README

Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [x] 2.1 Add a row for each alert to the alert table of the section "Alerting" of `k8s/README.md`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## Criteria

- Group 1: `ClaudeSpendDailyHigh` SHALL fire when the 24 hour increase of the spend of `claude-sonnet-5-5` is above 15 USD, also when a series resets in the window and when the spend is in two jobs, and SHALL stay quiet for a normal day.
- Group 1: `HostedSpendDailyHigh` SHALL fire when the 24 hour increase of the spend of all models is above 25 USD, and a model other than `claude-sonnet-5-5` SHALL NOT fire `ClaudeSpendDailyHigh`.
- Group 2: The alert table SHALL have a row for each alert of the group, and each row SHALL name the label `end_user`.

## Workflow follow-up

- Pending a person: set the thresholds again with the spend data of one month (#4222). The running Service image holds #4231 when its digest is newer than the merge. Until then the counter reads low for a hosted agent run.
