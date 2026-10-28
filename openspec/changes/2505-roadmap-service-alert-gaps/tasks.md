# Tasks

## 1. The counts of the last hour count a series that starts in the hour

- [ ] 1.1 Write the failing promtool cases in `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` (a sparse error series from before the hour, a new error series with one sample, a GitHub and a model request stream that start in the hour, a sparse GitHub request stream from before the hour) and pin the new expressions in `tests/test_k8s_monitoring_alerting.py`; see them fail with `uv run devops ci test tests/test_k8s_monitoring_alerting.py`, with promtool on `PATH` (`uv run devops install-tools --tool promtool`)
- [ ] 1.2 Change `RoadmapServiceJobsFailing`, `RoadmapServiceGitHubRequestsHigh` and `RoadmapServiceModelRequestsHigh` and the comment of the group in `k8s/monitoring/prometheus-values.yaml`; verify with `uv run devops ci test tests/test_k8s_monitoring_alerting.py`
- [ ] 1.3 Say in "Roadmap service", "Alerts" of `k8s/README.md` how the counts read a new series; no command, option or message changes, so `uv run devops docs generate --sync-readme` changes nothing; verify with `uv run devops docs check`

## 2. A lane of a new pod has a job start

- [ ] 2.1 Write the failing test `test_a_worker_sets_its_lanes_job_start_to_its_own_start_before_its_first_job` in `tests/test_server_service.py`, and the promtool case of a lane of a new pod; see the test fail with `uv run devops ci test tests/test_server_service.py`
- [ ] 2.2 Set the job start gauge of the lane in `RepoWorker.start` in `src/devops_cli/server/service.py`, and say what the gauge holds at `CONST_SERVICE_METRIC_JOB_START_TIMESTAMP`; verify with `uv run devops ci test tests/test_server_service.py tests/test_k8s_monitoring_alerting.py`
- [ ] 2.3 Say in the row of `RoadmapServiceLaneStalled` in `k8s/README.md` when the 2 hours of a new pod start; verify with `uv run devops docs check`

## Workflow follow-up

- #2506 makes Prometheus record a zero sample at the start of each series of the collector. Then plain `increase()` counts the first value, and these rules can go back to it.
- Pending a person: when the Service runs again, read the group `roadmap-service` on the Alerts page of Prometheus, and check that no alert of the group fires while the Service runs normally.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
