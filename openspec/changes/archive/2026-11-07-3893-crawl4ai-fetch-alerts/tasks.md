# Tasks

## 1. Alert on failed Crawl4AI fetches and on an unavailable Deployment

Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, `src/devops_cli/ai/page_text.py`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/crawl4ai_tests.yaml`.

- [x] 1.1 Write the tests of the group `crawl4ai`: the rule set, the selectors, the text of the fetch alert, the README pointer and the promtool fixture with a series that fires and series that do not
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] 1.2 Add the group `crawl4ai` with `Crawl4AIFetchesFailing` and `Crawl4AIUnavailable` to `k8s/monitoring/prometheus-values.yaml`
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## 2. List the alerts in the README

Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [x] 2.1 Add the table of the two alerts to the section "Crawl4AI" of `k8s/README.md`
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## Criteria

- Group 1: `Crawl4AIFetchesFailing` SHALL fire when at least 5 fetches failed in the last hour and more than half of the fetches of that hour failed, and SHALL stay quiet for fewer failures, for a smaller share, for a fetch with another job, and when the counter has no series.
- Group 1: `Crawl4AIUnavailable` SHALL fire after 15 minutes with no available replica while the Deployment wants one.
- Group 1: The text of `Crawl4AIFetchesFailing` SHALL name the label `result` and the two log commands.
- Group 2: The section "Crawl4AI" SHALL list both alerts.

## Workflow follow-up

- Pending a person: set `crawl4ai.url` in the live ConfigMap and sync the `devops` stack, so that the pod and the counter exist. Until then the Deployment rule has no series and the fetch rule has none.
