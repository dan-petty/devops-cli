# Tasks

## 1. Evaluate the hour-scale promtool cases once each hour

Kind: other. Changes: `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_activity_hourly_tests.yaml`.

- [x] 1.1 Add the guard test that fails a promtool case of more than 1,000 rounds, and the test that the files of each group test every alert of the group. On the base, the guard fails for `roadmap_service_activity_tests.yaml`.
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] 1.2 Move the 7 hour-scale test groups of `roadmap-service-activity` to `roadmap_service_activity_hourly_tests.yaml` with `evaluation_interval: 1h`, and let the promtool test run once for each file of a group
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## 2. Documents

Kind: other. Changes: `k8s/README.md`.

- [x] 2.1 List the new file in the promtool paragraph of `k8s/README.md`, with the rule for a case that runs for days
  - Verification: `$ uv run devops ci docs`
