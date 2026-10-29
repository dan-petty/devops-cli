# Tasks

## 1. The write rule counts only the write methods

- [x] 1.1 Write the failing promtool case of a series with no `method` label in `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, pin the new expression in `tests/test_k8s_monitoring_alerting.py`, and add `test_the_write_rule_names_each_write_method_of_the_request_classifier`; see them fail with `uv run pytest -q -n 0 tests/test_k8s_monitoring_alerting.py -k "promtool or fires or activity or write_rule"`, with promtool on `PATH` (`uv run devops install-tools --tool promtool`)
- [x] 1.2 Change the matcher of `RoadmapServiceGitHubWritesHigh` and the comment of the group in `k8s/monitoring/prometheus-values.yaml`; verify with `uv run devops ci test tests/test_k8s_monitoring_alerting.py` and the promtool cases
- [x] 1.3 Say in the row of `RoadmapServiceGitHubWritesHigh` in `k8s/README.md` which methods count, and use the selector of the rule in its query; no command, option or message changes, so `uv run devops docs generate --sync-readme` changes nothing; verify with `uv run devops docs check`

## Workflow follow-up

- Pending a person: after Argo CD applies the rule, read the group `roadmap-service-activity` on the Alerts page of Prometheus, and check that `RoadmapServiceGitHubWritesHigh` does not fire on the series with no `method` label.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
