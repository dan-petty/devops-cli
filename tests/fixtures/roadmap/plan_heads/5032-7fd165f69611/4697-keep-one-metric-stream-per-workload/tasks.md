# Tasks

## 1. Build the metric resource from the stable attribute set

Reads: `src/devops_cli/telemetry/tracer.py`, `tests/telemetry/test_telemetry.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/server/routes/test_k8s_roadmap_service.py`. Changes: `src/devops_cli/telemetry/tracer.py`, `tests/telemetry/test_telemetry.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/server/routes/test_k8s_roadmap_service.py`.

- [ ] 1.1 Write `test_two_tracers_with_one_instance_send_equal_metric_resources` in `tests/telemetry/test_telemetry.py` first: it starts two tracers with different platform.node() values and one OTEL_RESOURCE_ATTRIBUTES service.instance.id, and asserts equal metric Resources with no key outside the allowed set. It also rewrites `test_counters_are_monotonic_deltas_from_the_host_not_the_process` to assert that its metric Resource holds no host.name and keeps the instance from the variable, and `test_every_pod_of_the_deployment_exports_its_metrics_under_one_series_identity` to assert that both pods send one equal metric Resource with no host.name
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry.py tests/telemetry/test_telemetry_instruments.py tests/server/routes/test_k8s_roadmap_service.py` fails on the base
- [ ] 1.2 In `_ensure_meter`, build the Resource from service.name, service.instance.id, os.type, telemetry.sdk.name and telemetry.sdk.language, merge the SDK detector, and keep only service.name, service.namespace, service.instance.id, os.type and the keys under telemetry.sdk. Leave the span and log Resource as it is, with host.name, and add a test of a span that names the host while its metric Resource does not
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry.py tests/telemetry/test_telemetry_instruments.py tests/server/routes/test_k8s_roadmap_service.py` passes

## 2. Run one cluster Job of the workload at a time

Reads: `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/commands/k8s/cluster_jobs.py`, `src/devops_cli/k8s/cluster_job.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/commands/k8s/test_k8s_run_job.py`, `k8s/README.md`. Changes: `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/commands/k8s/cluster_jobs.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/commands/k8s/test_k8s_run_job.py`, `k8s/README.md`.

- [ ] 2.1 Write `test_a_round_waits_while_a_job_of_the_workload_runs` in `tests/roadmap/implement/test_roadmap_implement_submit.py` and `test_run_job_refuses_while_a_job_of_the_workload_has_not_ended` in `tests/commands/k8s/test_k8s_run_job.py` first: each lists a running Job that carries the label `app.kubernetes.io/name: devops-cli-job` of another repository, and asserts that the round reports waiting and that the command raises with the message that names the running Job
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py tests/commands/k8s/test_k8s_run_job.py` fails on the base
- [ ] 2.2 List the Jobs by `JOB_NAME_LABEL` and `JOB_NAME_LABEL_VALUE` before a Job is created. In `run_implement_round`, wait when any Job of the workload is running, beside the per-repository wait at the two sites the feasibility cites. In `execute_job`, raise a `ClusterJobError` that names the running Jobs, for both templates. Add the message beside `job_runner_running` in `MESSAGES.k8s`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py tests/commands/k8s/test_k8s_run_job.py` passes
- [ ] 2.3 Edit the runner guarantees in `k8s/README.md` to say that one Job of the workload runs at a time, so one process writes the metric stream, and run `uv run devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci docs` passes

## 3. Set one instance id in both CronJob templates

Reads: `k8s/devops/cronjob.yaml`, `k8s/devops/cronjob-runner.yaml`, `k8s/devops/roadmap-service/deployment.yaml`, `tests/config/test_k8s_devops_runtime.py`. Changes: `k8s/devops/cronjob.yaml`, `k8s/devops/cronjob-runner.yaml`, `tests/config/test_k8s_devops_runtime.py`, `tests/commands/k8s/test_k8s_devops_stack.py`, `tests/tools_lock/test_k8s_argo_workflows.py`, `tests/k8s/test_k8s_cluster_job_api.py`, `tests/roadmap/implement/test_roadmap_implement_deadline.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_typed_result.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, `tests/roadmap/test_roadmap_release_roll.py`, `tests/roadmap/test_roadmap_run_job_rows.py`, `tests/roadmap/test_roadmap_status_round.py`.

- [ ] 3.1 Write `test_both_cluster_job_templates_set_one_runner_instance` in `tests/config/test_k8s_devops_runtime.py` first: it reads both templates and asserts that each container holds OTEL_RESOURCE_ATTRIBUTES with the value service.instance.id=devops-cli-job beside OTEL_SERVICE_NAME=devops-cli-job, and it fails before the templates change
  - Verification: `$ uv run devops ci test tests/config/test_k8s_devops_runtime.py` fails on the base
- [ ] 3.2 Run that test red, then add OTEL_RESOURCE_ATTRIBUTES with the value service.instance.id=devops-cli-job to the container environment of both templates, below OTEL_SERVICE_NAME, with a comment that the Job pods of the workload then share one metric stream, as the Service Deployment does. The other test modules in `changes` read the two manifests and stay as they are unless the added variable breaks an assertion
  - Verification: `$ uv run devops ci test tests/config/test_k8s_devops_runtime.py` passes

## 4. Alert on two metric streams in one Prometheus series

Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/otel_collector_tests.yaml`, `k8s/README.md`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/fixtures/prometheus_rules/metric_streams_tests.yaml` (new), `tests/prometheus/test_k8s_monitoring_alerting.py`, `k8s/README.md`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_monitoring_integration.py`, `tests/commands/k8s/test_k8s_rag_ingest_manifests.py`, `tests/commands/k8s/test_stack_dashboards.py`, `tests/core/test_k8s_local_path_placement.py`, `tests/invariants/test_k8s_argocd_apps.py`, `tests/invariants/test_k8s_manifests.py`, `tests/prometheus/test_k8s_monitoring_dashboards.py`, `tests/roadmap/stage/test_roadmap_stage_manifest.py`.

- [ ] 4.1 Write the promtool case `Two streams share a job and instance fire` in `tests/fixtures/prometheus_rules/metric_streams_tests.yaml` first: two target_info series of job roadmap-service and instance roadmap-service, apart by host_name, for 40 minutes, fire at 31 minutes and stay quiet at 20. Add the case `One series or a short overlap stays quiet`: one series for 40 minutes, and two series where one ends as the other starts, which stays quiet
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [ ] 4.2 Add the group metric-streams with DevopsCliMetricStreamsShareSeries: count by (job, instance) (last_over_time(target_info{job=~"devops-cli.*|roadmap-service"}[15m])) > 1, for 30m, severity warning, with a summary that names the count and a description that names the resource attributes and the alert table. The case file names metric-streams.rules.yaml in rule_files and runs at a 1-minute interval, under MAX_PROMTOOL_ROUNDS. In `tests/prometheus/test_k8s_monitoring_alerting.py`, add the group and its file to RULE_GROUP_TESTS, target_info to SERVED_SERIES, the alert with warning to the baseline rule list, and a test that reads the row of the alert table. The other test modules in `changes` read `k8s/monitoring/prometheus-values.yaml` and stay as they are unless the added group breaks an assertion
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes
- [ ] 4.3 Add the row of `DevopsCliMetricStreamsShareSeries` to the alert table of `k8s/README.md`, with the job and instance labels, the 30-minute wait and the action
  - Verification: `$ uv run devops ci docs` passes

## 5. Describe the stable metric resource in the telemetry reference

Reads: `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`. Changes: `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`.

- [ ] 5.1 Rewrite the metric resource paragraph of `src/devops_cli/docs/generator.py`: the metric resource holds service.name, service.namespace, service.instance.id, os.type and telemetry.sdk.* only, host.name stays on spans and logs, roadmap-service sets service.instance.id=roadmap-service, and both CronJob templates set service.instance.id=devops-cli-job so the Job pods share one stream. Run `uv run devops docs generate` and keep only the regenerated reference
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Rewrite the metric resource paragraph of the generated reference `docs/TELEMETRY.md` through its source `src/devops_cli/docs/generator.py`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test shows that two tracers with different platform.node() values and the same OTEL_RESOURCE_ATTRIBUTES service.instance.id give equal metric Resources, and that the metric Resource holds no key outside the allowed set.
- Group 3: A test shows that both CronJob templates set service.instance.id=devops-cli-job.
- Group 4: promtool cases: the alert fires for two target_info series of one job and instance that stay for 30 min; it stays quiet over a 10 min overlap at a pod change and for one series.
- Pending person: Live, 24 h after the rollout: max(resets(devops_cli_github_requests_total{job='roadmap-service'}[24h])) is not more than the collector starts in that window (today 16, with 15 Service pod starts and 2 collector starts); count(count by (instance) (devops_cli_command_total{job='devops-cli-job'})) is 1., The check reads the live Prometheus 24 h after the rollout, so only a person can run the two queries and compare the counts.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
