# Tasks

## 1. Build the metric Resource from the stable attribute set

Kind: behavior. Reads: `src/devops_cli/telemetry/tracer.py`, `tests/telemetry/test_telemetry.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/server/routes/test_k8s_roadmap_service.py`. Changes: `src/devops_cli/telemetry/tracer.py`, `tests/telemetry/test_telemetry.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/server/routes/test_k8s_roadmap_service.py`.

- [x] 1.1 `test_two_tracers_with_one_instance_send_equal_metric_resources` in `tests/telemetry/test_telemetry.py`: two tracers with different platform.node() values and one OTEL_RESOURCE_ATTRIBUTES service.instance.id give equal metric Resources, with no key outside the allowed set
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry.py tests/telemetry/test_telemetry_instruments.py tests/server/routes/test_k8s_roadmap_service.py` fails on the base
- [x] 1.2 In `_ensure_meter`, build the Resource from service.name, service.instance.id, os.type, telemetry.sdk.name and telemetry.sdk.language, merge the SDK detector, and keep only service.name, service.namespace, service.instance.id, os.type and the keys under telemetry.sdk. Add the new test and a test that a span Resource still holds host.name while the metric Resource does not. Rewrite `test_counters_are_monotonic_deltas_from_the_host_not_the_process` in `tests/telemetry/test_telemetry_instruments.py` to assert that its metric Resource holds no host.name and keeps the instance from the variable, and `test_every_pod_of_the_deployment_exports_its_metrics_under_one_series_identity` in `tests/server/routes/test_k8s_roadmap_service.py` to assert that both pods send one equal metric Resource with no host.name
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry.py tests/telemetry/test_telemetry_instruments.py tests/server/routes/test_k8s_roadmap_service.py` passes

## 2. Set one runner instance in both CronJob templates

Kind: other. Reads: `k8s/devops/cronjob.yaml`, `k8s/devops/cronjob-runner.yaml`, `tests/config/test_k8s_devops_runtime.py`. Changes: `k8s/devops/cronjob.yaml`, `k8s/devops/cronjob-runner.yaml`, `tests/config/test_k8s_devops_runtime.py`, `tests/commands/k8s/test_k8s_devops_stack.py`, `tests/k8s/test_k8s_cluster_job_api.py`, `tests/roadmap/implement/test_roadmap_implement_deadline.py`, `tests/roadmap/implement/test_roadmap_implement_job_result.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_typed_result.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, `tests/roadmap/test_roadmap_release_roll.py`, `tests/roadmap/test_roadmap_run_job_rows.py`, `tests/roadmap/test_roadmap_status_round.py`, `tests/tools_lock/test_k8s_argo_workflows.py`.

- [x] 2.1 Add OTEL_RESOURCE_ATTRIBUTES with the value service.instance.id=devops-cli-job to the container env of `k8s/devops/cronjob.yaml` and of `k8s/devops/cronjob-runner.yaml`, beside OTEL_SERVICE_NAME, with a comment that says why: the metric stream of the workload continues across its Job pods. Add `test_both_cronjob_templates_set_the_runner_instance` to `tests/config/test_k8s_devops_runtime.py`: it reads both templates and asserts that each container sets OTEL_RESOURCE_ATTRIBUTES to service.instance.id=devops-cli-job, and that the value holds no secret. Read the other test modules of the group, which name the two templates, and update a count, a copied env list or an expected value there when the added variable makes it wrong
  - Verification: `$ uv run devops ci test tests/config/test_k8s_devops_runtime.py tests/commands/k8s/test_k8s_devops_stack.py tests/k8s/test_k8s_cluster_job_api.py` passes

## 3. Add the metric-streams rule group and its promtool cases

Kind: manifest. Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/otel_collector_tests.yaml`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/metric_streams_tests.yaml` (new), `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_monitoring_integration.py`, `tests/commands/k8s/test_k8s_rag_ingest_manifests.py`, `tests/commands/k8s/test_stack_dashboards.py`, `tests/core/test_k8s_local_path_placement.py`, `tests/invariants/test_k8s_argocd_apps.py`, `tests/invariants/test_k8s_manifests.py`, `tests/prometheus/test_k8s_monitoring_dashboards.py`, `tests/roadmap/stage/test_roadmap_stage_manifest.py`, `tests/roadmap/test_roadmap_plan_read.py`.

- [x] 3.1 The promtool case `Two target_info series of one job and instance fire after 30 minutes` in `tests/fixtures/prometheus_rules/metric_streams_tests.yaml`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [x] 3.2 Add the group metric-streams to `serverFiles.alerting_rules.yml` with the alert DevopsCliMetricStreamsShareSeries: expression count by (job, instance) (last_over_time(target_info{job=~"devops-cli.*|roadmap-service"}[15m])) > 1, for 30m, severity warning, and a summary and a description that name the job, the instance, the metric Resource attributes and the runbook row. In `tests/prometheus/test_k8s_monitoring_alerting.py`, add the group with its case file to RULE_GROUP_TESTS, target_info to SERVED_SERIES, and the alert with the warning severity to the baseline rule list. Create the case file with evaluation_interval 1m and three cases: two target_info series of one job and instance fire at 30 minutes with the job and instance labels; one series stays quiet; two series that overlap for 10 minutes stay quiet. Every case ends at or before 40 minutes, under MAX_PROMTOOL_ROUNDS. Read the other test modules of the group, which name `k8s/monitoring/prometheus-values.yaml`, and update a rule count, a group list or an expected alert set there when the new group makes it wrong
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## 4. Add the alert row to the runbook

Kind: other. Reads: `k8s/README.md`, `tests/prometheus/test_k8s_monitoring_alerting.py`. Changes: `k8s/README.md`, `tests/prometheus/test_k8s_monitoring_alerting.py`.

- [x] 4.1 Add a row for DevopsCliMetricStreamsShareSeries to the Alerting table of `k8s/README.md`: it fires when two target_info series of one job and instance stay for 30 minutes, it waits 30m, its severity is warning, and its action is to read the two series of that job and instance and remove the extra stream. Add `test_the_metric_streams_alert_has_a_row_in_the_readme` to `tests/prometheus/test_k8s_monitoring_alerting.py`, which reads the row and asserts the job, the instance and the action
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes
- [x] 4.2 Edit the Alerting table of `k8s/README.md` with the row of the new alert and its action
  - Verification: `$ uv run devops ci docs` passes

## 5. Describe the stable metric Resource in the telemetry reference

Kind: other. Reads: `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`. Changes: `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`.

- [x] 5.1 Rewrite the metric Resource paragraphs of `src/devops_cli/docs/generator.py`: the metric Resource holds service.name, service.namespace, service.instance.id, os.type and telemetry.sdk.* only; host.name stays on spans and logs; roadmap-service sets service.instance.id=roadmap-service; both CronJob templates set service.instance.id=devops-cli-job, so the Job pods of the workload share one stream. Run `uv run devops docs generate` and keep the regenerated `docs/TELEMETRY.md`
  - Verification: `$ uv run devops ci docs` passes
- [x] 5.2 Edit the telemetry section of `src/devops_cli/docs/generator.py` and regenerate `docs/TELEMETRY.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test shows that two tracers with different platform.node() values and the same OTEL_RESOURCE_ATTRIBUTES service.instance.id give equal metric Resources, and that the metric Resource holds no key outside the allowed set.
- Group 2: A test shows that both CronJob templates set service.instance.id=devops-cli-job.
- Group 3: promtool cases: the alert fires for two target_info series of one job and instance that stay for 30 min; it stays quiet over a 10 min overlap at a pod change and for one series.
- Pending person: Live, 24 h after the rollout: max(resets(devops_cli_github_requests_total{job='roadmap-service'}[24h])) is not more than the collector starts in that window (today 16, with 15 Service pod starts and 2 collector starts); count(count by (instance) (devops_cli_command_total{job='devops-cli-job'})) is 1., Only a person can read the production Prometheus over the 24 hours after the rollout, and the two counts name live series that no offline test reaches.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
