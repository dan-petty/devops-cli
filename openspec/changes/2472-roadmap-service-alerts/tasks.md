# Tasks

## 1. The roadmap Service has alert rules

- [x] 1.1 Write the failing tests of the group `roadmap-service` in `tests/test_k8s_monitoring_alerting.py` (the rule set, the expressions, the selectors, the two paths of the job, the kube-state-metrics allow list, the README pointer, `promtool check rules` and `promtool test rules`) and the promtool unit tests in `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`; see them fail with `uv run devops ci test tests/test_k8s_monitoring_alerting.py`
- [ ] 1.2 Add the group `roadmap-service` with its eight alerts to `k8s/monitoring/prometheus-values.yaml`; verify with `uv run devops ci test tests/test_k8s_monitoring_alerting.py`, and with `uv run devops install-tools --tool promtool` before it, so the two promtool tests run
- [ ] 1.3 Add the part "Alerts" to "Roadmap service" in `k8s/README.md`, with a row for each alert in the table of "Alerting"; no command, option or message changes, so `uv run devops docs generate --sync-readme` changes nothing; verify with `uv run devops docs check`

## 2. The CI test job runs promtool

- [x] 2.1 Write the failing test `test_the_test_job_installs_the_pinned_promtool_before_the_gate` in `tests/test_workflow_contracts.py`; see it fail with `uv run devops ci test tests/test_workflow_contracts.py`
- [ ] 2.2 Pin promtool 3.15.0 in `src/devops_cli/tools_lock/tools.lock` with the SHA-256 of each release archive, and add the step "Install promtool" before the gate of the test job in `.github/workflows/ci.yml`; verify with `uv run devops ci test tests/test_workflow_contracts.py tests/test_tools_lock.py tests/test_install_tools.py`, and with the CI test job, which runs the two promtool tests

## Workflow follow-up

- #1391 and #1392 route the alerts to Mattermost. Until then, no alert leaves the cluster. #1392 changes `RoadmapServiceJobsFailing` and adds no second rule with that name.
- Pending a person: when the Service runs again, read the group `roadmap-service` on the Alerts page of Prometheus, and check that no alert of the group fires while the Service runs normally.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
