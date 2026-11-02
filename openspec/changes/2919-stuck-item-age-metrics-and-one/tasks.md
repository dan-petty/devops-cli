# Tasks

## 1. Declare the roadmap age gauges

Reads: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [ ] 1.1 Add a test in tests/telemetry/test_telemetry_instruments.py that INSTRUMENTS holds the six state age gauges and the claim age gauge, and verify that `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` fails on the base
- [ ] 1.2 Add ROADMAP_ITEM_AGE and ROADMAP_CLAIM_AGE instruments as gauges in seconds, add them to INSTRUMENTS and __all__, and make the test pass, and verify that `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 2. Compute the age from the label event time

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/telemetry/instruments.py`. Changes: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_run.py`.

- [ ] 2.1 Add a test in tests/roadmap/test_roadmap_run.py that a label event at T with a fake clock at T plus 3600 emits 3600 on the state gauge, and verify that `uv run devops ci test tests/roadmap/test_roadmap_run.py` fails on the base
- [ ] 2.2 Read the label events of each open item, take the time of the event that set the state label, compute the age with an injectable clock, and emit the oldest age for each state and the oldest claim by repository, and verify that `uv run devops ci test tests/roadmap/test_roadmap_run.py` passes

## 3. Add the stuck-item alert rule and its unit test

Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`.

- [ ] 3.1 Add one alert rule over the roadmap age gauges for ready with a plan and blocked, with the item number in the message, and add its promtool unit test and the pin in the alerting test, and verify that `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## 4. Add the age panel to the dashboard

Reads: `k8s/monitoring/dashboards/project-metrics.json`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `k8s/monitoring/dashboards/project-metrics.json`.

- [ ] 4.1 Add a timeseries panel that reads the roadmap age gauges by state and repository, beside the inbox panel position, and verify that `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 5. Document the age metrics

Reads: `docs/TELEMETRY.md`, `src/devops_cli/telemetry/instruments.py`. Changes: `docs/TELEMETRY.md`.

- [ ] 5.1 Add the age gauges and the claim gauge to the metric table of docs/TELEMETRY.md, and verify that `uv run devops ci docs` passes
- [ ] 5.2 docs/TELEMETRY.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
