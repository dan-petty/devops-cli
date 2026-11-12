# Proposal

## Why

The metric Resource holds host.name, which is the pod name. The collector keys a metric stream by every resource attribute, but Prometheus keeps only job and instance, so each Service pod start and each runner Job pod begins a new total at zero in the same series. A new total that is not lower than the old one is not seen as a reset, so its counts are lost (#4697).

## What Changes

- Build the metric Resource in `src/devops_cli/telemetry/tracer.py` from service.name, service.namespace, service.instance.id, os.type and telemetry.sdk.* only, and keep no host.name in it.
- Read service.instance.id from OTEL_RESOURCE_ATTRIBUTES, so a workload sets one instance without a code change, and keep service.namespace when the environment sets it.
- Keep host.name on the span and log Resource, which still names the pod.
- Make the cluster Job workload single-writer: a round of the implement row waits, and `devops k8s run-job` refuses, while any Job of `devops-cli-job` has not ended.
- Set OTEL_RESOURCE_ATTRIBUTES to service.instance.id=devops-cli-job in `k8s/devops/cronjob.yaml` and `k8s/devops/cronjob-runner.yaml`.
- Add the rule group metric-streams with DevopsCliMetricStreamsShareSeries to `k8s/monitoring/prometheus-values.yaml`.
- Add the promtool cases in `tests/fixtures/prometheus_rules/metric_streams_tests.yaml`, list target_info in SERVED_SERIES and add the alert to the baseline rule list, and list every test module that reads the manifest in the same group.
- Add the row of the alert to the alert table of `k8s/README.md`.
- Rewrite the metric resource paragraph of the generated `docs/TELEMETRY.md` through its source `src/devops_cli/docs/generator.py`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `metric-stream-alerts`: Two streams in one series fire, One stream or a short overlap stays quiet, The alert selects only a served series, The rule set and its promtool file list the alert, The runbook names the alert

### Modified Capabilities

- `metric-instruments`: The metric resource carries only stable attributes, The metric resource reads the configured instance, One cluster Job writes a metric stream at a time
- `command-telemetry`: The span resource keeps the host name

## Impact

- Code: `src/devops_cli/telemetry/tracer.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/commands/k8s/cluster_jobs.py`, `src/devops_cli/lang/en/messages.py`, `k8s/devops/cronjob.yaml`, `k8s/devops/cronjob-runner.yaml`, `k8s/monitoring/prometheus-values.yaml`, `src/devops_cli/docs/generator.py`
- Documents: `k8s/README.md`, `docs/TELEMETRY.md`
- Tests: `tests/telemetry/test_telemetry.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/server/routes/test_k8s_roadmap_service.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/commands/k8s/test_k8s_run_job.py`, `tests/config/test_k8s_devops_runtime.py`, `tests/commands/k8s/test_k8s_devops_stack.py`, `tests/tools_lock/test_k8s_argo_workflows.py`, `tests/k8s/test_k8s_cluster_job_api.py`, `tests/roadmap/implement/test_roadmap_implement_deadline.py`, `tests/roadmap/implement/test_roadmap_implement_typed_result.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, `tests/roadmap/test_roadmap_release_roll.py`, `tests/roadmap/test_roadmap_run_job_rows.py`, `tests/roadmap/test_roadmap_status_round.py`, `tests/fixtures/prometheus_rules/metric_streams_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_monitoring_integration.py`, `tests/commands/k8s/test_k8s_rag_ingest_manifests.py`, `tests/commands/k8s/test_stack_dashboards.py`, `tests/core/test_k8s_local_path_placement.py`, `tests/invariants/test_k8s_argocd_apps.py`, `tests/invariants/test_k8s_manifests.py`, `tests/prometheus/test_k8s_monitoring_dashboards.py`, `tests/roadmap/stage/test_roadmap_stage_manifest.py`

## Feasibility

- The probes confirm the three cited files: "The path `src/devops_cli/telemetry/tracer.py` is a file of the staging commit.", "The path `k8s/devops/cronjob.yaml` is a file of the staging commit." and "The path `k8s/devops/cronjob-runner.yaml` is a file of the staging commit."
- The probes also say "The path `service.instance.id` is no file of the staging commit. No commit in the history deleted or renamed it." and "The path `host.name` is no file of the staging commit. No commit in the history deleted or renamed it.", and the same of `os.type`: they are resource attribute names, so no file is expected.
- search_code for `"service.instance.id": self.host_name` returned one hit, `src/devops_cli/telemetry/tracer.py:1061:"service.instance.id": self.host_name,`, and read_file of lines 1020 to 1090 shows the metric Resource at `src/devops_cli/telemetry/tracer.py:1058:resource = Resource(` with `src/devops_cli/telemetry/tracer.py:1062:"host.name": self.host_name,`.
- The same read shows the meter is built once in `src/devops_cli/telemetry/tracer.py:1030:def _ensure_meter(self) -> Any:` and that the SDK detector merges last at `src/devops_cli/telemetry/tracer.py:1067:).merge(OTELResourceDetector().detect())`, so a filter over the merged set keeps the instance that OTEL_RESOURCE_ATTRIBUTES sets.
- The span Resource keeps the pod name at `src/devops_cli/telemetry/tracer.py:924:{"key": "host.name", "value": {"stringValue": self.host_name}},`, which the change leaves alone.
- Two tests assert today's identity and change with the Resource: `tests/telemetry/test_telemetry_instruments.py:930:resource["service.instance.id"] == resource["host.name"],` and `tests/server/routes/test_k8s_roadmap_service.py:198:(resource["service.name"], resource["service.instance.id"], resource["host.name"])`.
- The context quotes both templates with only the service name, and my read_file of `k8s/devops/cronjob.yaml` lines 55 to 62 confirms `k8s/devops/cronjob.yaml:58:- name: OTEL_SERVICE_NAME` with `k8s/devops/cronjob.yaml:59:value: devops-cli-job`, and my read of `k8s/devops/cronjob-runner.yaml` confirms `k8s/devops/cronjob-runner.yaml:66:- name: OTEL_SERVICE_NAME` with `k8s/devops/cronjob-runner.yaml:67:value: devops-cli-job`. Neither template sets OTEL_RESOURCE_ATTRIBUTES.
- search_code for `service.instance.id` shows the setting the templates take: `k8s/devops/roadmap-service/deployment.yaml:88:- name: OTEL_RESOURCE_ATTRIBUTES` with `k8s/devops/roadmap-service/deployment.yaml:89:value: service.instance.id=roadmap-service`.
- read_issue 2039 answered closed (completed) with no merged pull request that closed it, and its archived design rejected this exact alternative at `openspec/changes/archive/2026-10-27-2039-job-metrics-increase/design.md:20:- Force cluster jobs to share a single instance identifier (which causes out-of-order delta drops during concurrent runs).` The plan does not repeat that rejected premise.
- search_code for `concurrencyPolicy` returned `k8s/devops/cronjob.yaml:14:concurrencyPolicy: Allow` and `k8s/devops/cronjob-runner.yaml:18:concurrencyPolicy: Forbid`, and `k8s/devops/cronjob.yaml:13:suspend: true` shows the CronJob never runs on its schedule. A concurrencyPolicy governs only the Jobs that a CronJob's own schedule creates, so it guards no Job that `devops k8s run-job` or the Service makes, and the plan does not use it as the guard.
- The answer to the false premise is group 2, a single-writer guard over the workload. read_file of `src/devops_cli/roadmap/implement/implement_submit.py` shows the per-repository wait at `src/devops_cli/roadmap/implement/implement_submit.py:517:if any(job.state is JobState.RUNNING for job in held.values()):` and `src/devops_cli/roadmap/implement/implement_submit.py:534:if _runs(api, label):`, and read_file of `src/devops_cli/commands/k8s/cluster_jobs.py` shows the same lock in the CLI at `src/devops_cli/commands/k8s/cluster_jobs.py:316:if labels and (running := _running_jobs(context, labels)):`. Group 2 widens both to every Job of the workload, so two pods of `devops-cli-job` never write one stream at once.
- The plan relies on two constants of the staged tree: `JOB_NAME_LABEL = "app.kubernetes.io/name"` at `src/devops_cli/k8s/cluster_job.py:24:JOB_NAME_LABEL = "app.kubernetes.io/name"`, and `JOB_NAME_LABEL_VALUE = "devops-cli-job"` at `src/devops_cli/k8s/cluster_job.py:25:JOB_NAME_LABEL_VALUE = "devops-cli-job"`.
- search_code for `deltatocumulative` lists the archived change folder of #4684, so the dependency of the issue is delivered, and find_issues for `OTEL_RESOURCE_ATTRIBUTES metric stream` listed only #4697, so no open item overlaps this change.
- search_code for `unique instance names` shows the generated reference states the host-name identity at `src/devops_cli/docs/generator.py:1110:"Cluster job pods have unique instance names and export metrics only once when they exit.",` and `docs/TELEMETRY.md:29:Cluster job pods have unique instance names and export metrics only once when they exit.`, so the change rewrites that paragraph in its source and regenerates the document.
- read_file of `tests/prometheus/test_k8s_monitoring_alerting.py` lines 118 to 175 shows where the alert joins: `tests/prometheus/test_k8s_monitoring_alerting.py:127:RULE_GROUP_TESTS = (`, `tests/prometheus/test_k8s_monitoring_alerting.py:139:MAX_PROMTOOL_ROUNDS = 1_000` and `tests/prometheus/test_k8s_monitoring_alerting.py:142:SERVED_SERIES = frozenset(`, and lines 330 to 400 show the baseline pin at `tests/prometheus/test_k8s_monitoring_alerting.py:359:("OtelCollectorExportFailing", "warning"),`.
- read_file of `tests/fixtures/prometheus_rules/otel_collector_tests.yaml` shows the case file format: the file names its rule file at `tests/fixtures/prometheus_rules/otel_collector_tests.yaml:12:rule_files:`.
- read_file of `k8s/README.md` lines 480 to 520 shows the alert table at `k8s/README.md:483:| Alert | Fires when | For | Severity |`, which is where the new row goes.
- The verify of the template group now runs one path, `tests/config/test_k8s_devops_runtime.py`, because the verify of a manifest group takes one path of the group.
- list_files of `tests/commands/k8s`, `tests/core`, `tests/invariants`, `tests/prometheus`, `tests/roadmap/stage` and `tests/config` confirmed each test module that the alert group lists beside the manifest: `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_monitoring_integration.py`, `tests/commands/k8s/test_k8s_rag_ingest_manifests.py`, `tests/commands/k8s/test_stack_dashboards.py`, `tests/core/test_k8s_local_path_placement.py`, `tests/invariants/test_k8s_argocd_apps.py`, `tests/invariants/test_k8s_manifests.py`, `tests/prometheus/test_k8s_monitoring_dashboards.py`, `tests/roadmap/stage/test_roadmap_stage_manifest.py` and `tests/config/test_k8s_devops_runtime.py`.
- Preconditions of the calls: `ClusterJobs.list_jobs` needs a client of the Kubernetes API, and `tests/roadmap/implement/test_roadmap_implement_submit.py` passes a fake, so no cluster is reached. `execute_job` needs `kubectl` and a network to the cluster, and `tests/commands/k8s/test_k8s_run_job.py` fakes the kubectl call. `_ensure_meter` needs no checkout, client or network: the telemetry tests read the metric Resource in process.
- No command and no verify program is new. The groups run `uv run devops ci test` and `uv run devops ci docs`, and the promtool cases run through the existing live test marked promtool. `promtool` is in the runner image, and the pod settings apply unchanged: readOnlyRootFilesystem true, runAsNonRoot true, allowPrivilegeEscalation false, capabilities drop ALL, seccompProfile RuntimeDefault. No new failure class is needed.
- The fourth acceptance criterion reads live Prometheus 24 h after the rollout, so no offline test asserts it and the plan leaves it to a person.

## Existing Tool Considered

The OpenTelemetry SDK Resource and OTEL_RESOURCE_ATTRIBUTES, which the repository already uses, plus promtool for the alert cases and the Prometheus alert rules of the chart. The change builds no tool and deletes no internal code.

## Dependencies

- devops_cli_command_total: src/devops_cli/telemetry/instruments.py, src/devops_cli/docs/generator.py, docs/TELEMETRY.md, k8s/monitoring/prometheus-values.yaml, tests/telemetry/test_telemetry.py and tests/telemetry/test_telemetry_instruments.py also hold this metric.
- devops_cli_github_requests_total: src/devops_cli/telemetry/instruments.py, src/devops_cli/docs/generator.py, k8s/monitoring/prometheus-values.yaml, k8s/README.md, tests/prometheus/test_k8s_monitoring_alerting.py and tests/telemetry/test_telemetry_instruments.py also hold this metric.
