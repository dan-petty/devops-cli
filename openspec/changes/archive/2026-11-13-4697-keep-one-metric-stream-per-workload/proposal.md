# Proposal

## Why

Prometheus kept one series for each job and instance, and every Service pod start and every runner Job pod began a new total at zero in it, so the counts that did not drop were lost. The metric Resource carried host.name, which is the pod name, and the collector keys a metric stream by every resource attribute. This change keeps one metric stream for each workload and adds the alert that fires if two streams write one Prometheus series again (#4697).

## What Changes

- Build the metric Resource from service.name, service.namespace, service.instance.id, os.type and telemetry.sdk.* only, and keep no host.name in it, in `src/devops_cli/telemetry/tracer.py`.
- Keep host.name on the span and log Resource, which still names the pod.
- Read service.instance.id from OTEL_RESOURCE_ATTRIBUTES, so a workload sets one stable instance with no code change.
- Set OTEL_RESOURCE_ATTRIBUTES to service.instance.id=devops-cli-job in `k8s/devops/cronjob.yaml` and `k8s/devops/cronjob-runner.yaml`, and update the tests that name those two templates.
- Add the rule group metric-streams with DevopsCliMetricStreamsShareSeries to `k8s/monitoring/prometheus-values.yaml`, and update the tests that name that file.
- Create `tests/fixtures/prometheus_rules/metric_streams_tests.yaml`, list target_info in the served series, and pin the alert in the baseline rule set.
- Add the row of the new alert to the Alerting table of `k8s/README.md`.
- Rewrite the metric Resource paragraphs of `src/devops_cli/docs/generator.py` and regenerate `docs/TELEMETRY.md` with `uv run devops docs generate`.
- Update `tests/telemetry/test_telemetry.py`, `tests/telemetry/test_telemetry_instruments.py` and `tests/server/routes/test_k8s_roadmap_service.py` for the new metric identity.
- The change carries a spec delta: the metric Resource identity, the CronJob instance and the alert rule are behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-telemetry`: The metric Resource holds only stable attributes, The metric Resource reads the configured instance, Both CronJob templates name one runner instance, Two metric streams in one Prometheus series fire an alert, One stream and a short overlap stay quiet, The alert selects only a served series, The rule set, the case file and the runbook list the alert

## Impact

- Code: `src/devops_cli/telemetry/tracer.py`, `k8s/devops/cronjob.yaml`, `k8s/devops/cronjob-runner.yaml`, `k8s/monitoring/prometheus-values.yaml`, `src/devops_cli/docs/generator.py`
- Documents: `k8s/README.md`, `docs/TELEMETRY.md`
- Tests: `tests/telemetry/test_telemetry.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/server/routes/test_k8s_roadmap_service.py`, `tests/config/test_k8s_devops_runtime.py`, `tests/commands/k8s/test_k8s_devops_stack.py`, `tests/k8s/test_k8s_cluster_job_api.py`, `tests/roadmap/implement/test_roadmap_implement_deadline.py`, `tests/roadmap/implement/test_roadmap_implement_job_result.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_typed_result.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, `tests/roadmap/test_roadmap_release_roll.py`, `tests/roadmap/test_roadmap_run_job_rows.py`, `tests/roadmap/test_roadmap_status_round.py`, `tests/tools_lock/test_k8s_argo_workflows.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/metric_streams_tests.yaml`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_monitoring_integration.py`, `tests/commands/k8s/test_k8s_rag_ingest_manifests.py`, `tests/commands/k8s/test_stack_dashboards.py`, `tests/core/test_k8s_local_path_placement.py`, `tests/invariants/test_k8s_argocd_apps.py`, `tests/invariants/test_k8s_manifests.py`, `tests/prometheus/test_k8s_monitoring_dashboards.py`, `tests/roadmap/stage/test_roadmap_stage_manifest.py`, `tests/roadmap/test_roadmap_plan_read.py`

## Feasibility

- The probe lines confirm the premise, word for word: "The path `src/devops_cli/telemetry/tracer.py` is a file of the staging commit.", "The path `k8s/devops/cronjob.yaml` is a file of the staging commit." and "The path `k8s/devops/cronjob-runner.yaml` is a file of the staging commit."
- The probe adds "The path `service.instance.id` is no file of the staging commit. No commit in the history deleted or renamed it.", and the same line for `host.name` and `os.type`: they are resource attribute names, so no file is expected.
- The probe says "Not probed, the bound of 10 commands is reached" for `k8s/monitoring/prometheus-values.yaml`, `k8s/README.md`, `tests/telemetry/test_telemetry.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/config/test_k8s_devops_runtime.py`, `docs/TELEMETRY.md` and `k8s/devops/roadmap-service/deployment.yaml`. This run read `k8s/monitoring/prometheus-values.yaml` and `tests/prometheus/test_k8s_monitoring_alerting.py` with `read_file`, and `k8s/devops/roadmap-service/deployment.yaml` only through a `search_code` hit; `k8s/README.md`, `tests/telemetry/test_telemetry.py`, `tests/config/test_k8s_devops_runtime.py` and `docs/TELEMETRY.md` are `not checked` by a read of this run.
- `read_file` of `src/devops_cli/telemetry/tracer.py` lines 1040 to 1080 of this run shows the metric Resource at `src/devops_cli/telemetry/tracer.py:1058:resource = Resource(`, with `src/devops_cli/telemetry/tracer.py:1061:"service.instance.id": self.host_name,` and `src/devops_cli/telemetry/tracer.py:1062:"host.name": self.host_name,`, and the SDK detector merged last at `src/devops_cli/telemetry/tracer.py:1067:).merge(OTELResourceDetector().detect())`, so a filter over the merged set keeps the instance that the variable sets.
- `read_file` of `k8s/devops/cronjob.yaml` lines 50 to 70 of this run shows `k8s/devops/cronjob.yaml:58:- name: OTEL_SERVICE_NAME` with `k8s/devops/cronjob.yaml:59:value: devops-cli-job`, and no OTEL_RESOURCE_ATTRIBUTES in the container env.
- `read_file` of `k8s/devops/cronjob-runner.yaml` lines 50 to 80 of this run shows `k8s/devops/cronjob-runner.yaml:66:- name: OTEL_SERVICE_NAME` with `k8s/devops/cronjob-runner.yaml:67:value: devops-cli-job`, and no OTEL_RESOURCE_ATTRIBUTES in the container env.
- `search_code` for `service.instance.id` of this run shows that the Service already sets one: `k8s/devops/roadmap-service/deployment.yaml:89:value: service.instance.id=roadmap-service`.
- `read_file` of `k8s/monitoring/prometheus-values.yaml` lines 560 to 620 of this run shows the rule groups of `serverFiles.alerting_rules.yml`, with `k8s/monitoring/prometheus-values.yaml:575:- name: otel-collector` and its two export-health rules at a 15-minute wait, so the new group is added beside them.
- `read_file` of `tests/prometheus/test_k8s_monitoring_alerting.py` lines 125 to 160 of this run shows where the alert joins: `tests/prometheus/test_k8s_monitoring_alerting.py:131:RULE_GROUP_TESTS = (`, `tests/prometheus/test_k8s_monitoring_alerting.py:144:MAX_PROMTOOL_ROUNDS = 1_000` and `tests/prometheus/test_k8s_monitoring_alerting.py:147:SERVED_SERIES = frozenset(`.
- The constant that the plan relies on is `MAX_PROMTOOL_ROUNDS` at `tests/prometheus/test_k8s_monitoring_alerting.py:144:MAX_PROMTOOL_ROUNDS = 1_000`: the longest new case ends at 40 minutes at a 1-minute interval, which is 40 rounds.
- The rejected plan ran a docs command with an option that #5198 removed. This plan names only `uv run devops docs generate`, the staged value at `src/devops_cli/roadmap/stage/stage_change.py:261:REGENERATE_DOCUMENTS: Final[str] = "uv run devops docs generate"`, and no text, task or verify command of this plan names a removed option.
- `search_code` for `service.instance.id` of this run shows the generated text that states today's behavior at `src/devops_cli/docs/generator.py:979:is the host name,`, and the same sentence at `docs/TELEMETRY.md:19:Prometheus names a series by`, so the generator text and its output change with the metric Resource.
- `list_files` of this run of `tests/roadmap/implement`, `tests/commands/k8s`, `tests/roadmap`, `tests/roadmap/stage`, `tests/invariants`, `tests/prometheus`, `tests/k8s`, `tests/tools_lock`, `tests/core`, `tests/telemetry`, `tests/config`, `tests/server/routes` and `tests/fixtures/prometheus_rules` shows each path that a group of this plan changes, and `tests/fixtures/prometheus_rules/metric_streams_tests.yaml` is the one path that does not exist yet.
- The review found that test modules name the manifests this change edits. Group 2 lists the tests that name `k8s/devops/cronjob.yaml` and `k8s/devops/cronjob-runner.yaml`, and group 3 lists the tests that name `k8s/monitoring/prometheus-values.yaml`, so the implement job can edit each of them.
- No function that the plan calls takes a client or a network: `uv run devops ci test`, `uv run devops ci docs` and `uv run devops docs generate` need a checkout of the repository.
- The verify commands need `uv`, `python`, `pytest` and `promtool`, each in the runner image (Runner tools lists `uv`, `python`, `pytest` and `promtool`) and none is `NOT_IN_RUNNER`. The promtool cases run under the pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`, and the tests write only under pytest's temporary directory.
- The plan introduces no new failure class: the verify commands are existing rows of `devops ci`, and a failure is a failing test or a document out of date with its generator.
- First checks against the real system: `uv run devops ci test tests/telemetry/test_telemetry.py`, `uv run devops ci test tests/config/test_k8s_devops_runtime.py`, `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` and `uv run devops ci docs`.
- The context lists the senders of `devops_cli_command_total` and `devops_cli_github_requests_total` and no open pull request that changes a cited path, so no overlap blocks this change and the plan changes no sender.
- `read_issue` of this run reports #4684 as closed (completed) and live since 2026-11-12 05:27 UTC, so the OTLP receiver of Prometheus and its created-timestamp feature are in place; #1629 is closed (completed) and set the instance of the Service.

## Existing Tool Considered

The OpenTelemetry SDK Resource and the standard `OTEL_RESOURCE_ATTRIBUTES` setting carry the resource filter, and a Prometheus alert rule with promtool cases carries the duplicate-stream check. The change builds no tool of its own.

## Dependencies

- `devops_cli_command_total`: the other files that hold it are `docs/SELF_IMPROVEMENT.md`, `docs/TELEMETRY.md`, `k8s/monitoring/dashboards/devops-cli.json`, `k8s/monitoring/prometheus-values.yaml`, `openspec/specs/command-telemetry/spec.md`, `src/devops_cli/docs/generator.py`, `src/devops_cli/telemetry/instruments.py`, `tests/fixtures/dashboard_queries/devops-cli.yaml`, `tests/grafana/test_grafana_dashboards.py`, `tests/telemetry/test_telemetry.py`, `tests/telemetry/test_telemetry_instruments.py`, and the archived change folders and plan-head fixtures under `openspec/changes/archive/` and `tests/fixtures/roadmap/plan_heads/`.
- `devops_cli_github_requests_total`: the other files that hold it are `docs/TELEMETRY.md`, `k8s/README.md`, `k8s/monitoring/dashboards/devops-cli.json`, `k8s/monitoring/prometheus-values.yaml`, `openspec/specs/command-telemetry/spec.md`, `openspec/specs/github-api-metrics/spec.md`, `openspec/specs/roadmap-service-limits/spec.md`, `src/devops_cli/docs/generator.py`, `src/devops_cli/github/client.py`, `src/devops_cli/github/rate_limiter.py`, `src/devops_cli/github/request_scope.py`, `src/devops_cli/telemetry/instruments.py`, `tests/fixtures/dashboard_queries/devops-cli.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, and the archived change folders and plan-head fixtures under `openspec/changes/archive/` and `tests/fixtures/roadmap/plan_heads/`.
