# Proposal

## Why

The owner asked on 2026-11-11 that the Service dashboard show the service jobs, the branch and the work log (#4621). A person cannot see which Service Job runs, for which repository and item, on which branch and working copy, or what it wrote, without kubectl and a hand-written Loki query. The Service dashboard is Grafana as code, so the view belongs in its generated panels and in the Job metadata that kube-state-metrics exports.

## What Changes

- Add the annotations roadmap.devops-cli/branch and roadmap.devops-cli/worktree to each stage Job and each implement Job of an item, from the branch of the target and the clone path of the round that submits the Job.
- Keep the families kube_job_labels, kube_job_annotations, kube_job_status_active, kube_job_status_start_time and kube_job_status_completion_time in the kube-state-metrics keep list of `k8s/monitoring/k8s-monitoring-values.yaml`, and allow the four Job labels and the two Job annotations in its label and annotation allowlists.
- Build a Service jobs table with nine columns and two GitHub data links, and a Work log panel on the Loki data source, in the template of `src/devops_cli/grafana/service_dashboard.py` behind a `jobs` field of `src/devops_cli/grafana/service_specs.py`.
- Offer the repo, item and job variables, filter the table on all three and the log panel on job.
- Turn the Job panels on for the Roadmap Service in `k8s/monitoring/dashboards/services.toml` and regenerate `k8s/monitoring/dashboards/devops-roadmap-service.json` with `make dashboards`.
- Add a check to the k8s row of `devops ci` that fails with the panel title and the key when a panel query reads a Job metric family, label or annotation that the monitoring values do not keep or allow.
- Add a case to `tests/telemetry/test_service_counter_series.py` that primes the Service counters and reads the label sets of the metrics registry, so no Service series carries a label named item, branch or worktree.
- Describe the panels, the annotations and the keep list and allowlists in `k8s/README.md`, and update the Service dashboard row of `docs/DESIGN.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `service-dashboard-template`: The Service jobs table shows the live Jobs of the Service, The Work log panel shows the lines of the selected Job, The Job panels filter on the repo, item and job variables, The dashboard check refuses a Job key or family that the monitoring values do not export
- `monitoring-collectors`: kube-state-metrics keeps the Service Job series and their keys
- `roadmap-stage/job`: The stage Job names its branch and its lane clone
- `roadmap-implement-job/runner-job`: The runner Job names its branch and its lane clone
- `metric-instruments`: The item, branch and worktree values stay off the Service series

## Impact

- Code: `src/devops_cli/k8s/cluster_job.py`, `src/devops_cli/roadmap/stage/stage_submit.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `k8s/monitoring/k8s-monitoring-values.yaml`, `src/devops_cli/grafana/service_specs.py`, `src/devops_cli/grafana/service_dashboard.py`, `k8s/monitoring/dashboards/services.toml`, `k8s/monitoring/dashboards/devops-roadmap-service.json`
- Documents: `k8s/README.md`, `docs/DESIGN.md`
- Tests: `tests/telemetry/test_service_counter_series.py`, `tests/roadmap/stage/test_roadmap_stage_submit.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/grafana/test_service_dashboard.py`, `tests/gate/k8s_checks/dashboard_job_keys.py`

## Feasibility

- `probes` gives, word for word: The path `src/devops_cli/k8s/cluster_job.py` is a file of the staging commit. `read_file` showed `src/devops_cli/k8s/cluster_job.py:38:JOB_NAMESPACE = "devops"` and the symbol `src/devops_cli/k8s/cluster_job.py:def build_job`, whose `annotations` keyword copies one mapping onto the Job and onto its pod template, so the two new keys reach both objects with no new parameter.
- `probes` gives, word for word: The path `k8s/monitoring/k8s-monitoring-values.yaml` is a file of the staging commit. `read_file` of lines 60 to 95 showed `k8s/monitoring/k8s-monitoring-values.yaml:65:includeMetrics:` with each family named in the list, such as `k8s/monitoring/k8s-monitoring-values.yaml:66:- kube_deployment_labels` and `k8s/monitoring/k8s-monitoring-values.yaml:69:- kube_horizontalpodautoscaler_labels`, and no kube_job family. `read_file` of lines 265 to 300 showed `k8s/monitoring/k8s-monitoring-values.yaml:275:metricLabelsAllowlist:` with one entry for each resource and no jobs entry.
- `read_file` of `tests/prometheus/test_k8s_monitoring_alerting.py:225` showed `# Not in the chart's default allow list:` and the rest of that line, which says that `metricsTuning.includeMetrics` keeps a family the default list drops. So the chart's default allow list is a curated list, and group 4 adds the five kube_job families to the keep list of the values instead of assuming that the default list holds them.
- `probes` gives, word for word: The path `services.toml` is no file at the root of the staging commit. These files of the commit are candidates: `k8s/monitoring/dashboards/services.toml`. `read_file` of that file showed the table `uid = "devops-roadmap-service"`, which group 5 gives the `jobs` field.
- `read_file` of `src/devops_cli/roadmap/stage/stage_submit.py:345:source: Path | str,` showed the clone of the stage round, and `src/devops_cli/roadmap/stage/stage_submit.py:329:labels=stage_job_labels(ref, item.number),` showed the create call with no annotations keyword. `src/devops_cli/roadmap/stage/stage.py:517:def branch(self) -> str:` gives the branch of the target, so group 2 passes both values into `_submit`.
- `read_file` of `src/devops_cli/roadmap/implement/implement_submit.py:694:source: Path | str,` showed the clone of the implement round, and `src/devops_cli/roadmap/implement/implement_submit.py:557:annotations={` showed the annotations mapping of the implement Job. `src/devops_cli/roadmap/implement/implement.py:184:branch: str` gives the branch of the target, so group 3 passes the clone into `_create` and adds the two keys there.
- `read_file` of `src/devops_cli/grafana/service_specs.py:54:logs: bool = True` showed the field shape that the new `jobs` field follows, and `src/devops_cli/grafana/service_dashboard.py:def _logs` showed the pod in a label filter after the stream selector, which the Work log panel follows.
- `read_file` of `tests/grafana/test_service_dashboard.py:243:assert (len(panels), [line for panel in panels for line in _panel_problems(panel)]) == (17, [])` showed the 17 panels of a spec without the new field, so the `jobs` field defaults to false and the two Job panels join the Roadmap Service dashboard only.
- `read_file` of `tests/telemetry/test_telemetry_instruments.py:87:SERVICE_SERIES: dict[str, InstrumentKind] = {` through its closing brace at line 111 showed 23 entries, each a series name and its kind, and no label set, so the new case walks the metrics registry and not this mapping. The module docstring line `src/devops_cli/telemetry/instruments.py:12:are declared in the config constants and are no instrument of this module.` says that the Service series are no instrument of that module.
- The set of the claim is the 23 series of `SERVICE_SERIES`, counted from line 88 through line 110 of `tests/telemetry/test_telemetry_instruments.py` with `read_file`. All 23 members are allowlisted unchanged, each for the same reason: this change adds no label to any instrument. The members: `CONST_SERVICE_METRIC_BUDGET_HOLDS`, `CONST_SERVICE_METRIC_BUDGET_LIMIT`, `CONST_SERVICE_METRIC_BUDGET_SPENT`, `CONST_SERVICE_METRIC_CHAT_COMMANDS`, `CONST_SERVICE_METRIC_IDENTITY_REFUSED`, `CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES`, `CONST_SERVICE_METRIC_IMPLEMENT_FAILURES`, `CONST_SERVICE_METRIC_IMPLEMENT_JOBS`, `CONST_SERVICE_METRIC_IMPLEMENT_REPAIR_ROUNDS`, `CONST_SERVICE_METRIC_IMPLEMENT_TOKENS`, `CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS`, `CONST_SERVICE_METRIC_JOB_SECONDS`, `CONST_SERVICE_METRIC_JOB_START_TIMESTAMP`, `CONST_SERVICE_METRIC_JOB_SUSPENDED`, `CONST_SERVICE_METRIC_JOBS`, `CONST_SERVICE_METRIC_QUEUE_DEPTH`, `CONST_SERVICE_METRIC_ROADMAP_ITEMS_CLOSED`, `CONST_SERVICE_METRIC_STAGE_JOBS`, `CONST_SERVICE_METRIC_FIX_CHECKS_JOBS`, `devops_cli_service_state_unkept`, `CONST_SERVICE_METRIC_TRIGGERS`, `CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES`, `CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES`.
- `read_file` of `src/devops_cli/roadmap/run.py:def _count_job` showed the labels it counts, `src/devops_cli/roadmap/run.py:2111:labels={"repo": repo, "lane": lane, "row": row, "result": result},`, and `src/devops_cli/server/counter_series.py:def prime_service_counters` creates each bounded label set of the Service counters at zero, so the registry of a started Service holds the label sets that the new case walks.
- `k8s/monitoring/k8s-monitoring-values.yaml:65:includeMetrics:` holds no kube_job family, so group 4 adds the five families to the keep list, and group 6 fails when a panel reads a family that the keep list does not hold.
- The new case of group 1 reads the label sets of the registry with the helper `tests/telemetry/test_service_counter_series.py:def _series` and starts the Service manager, so it walks real label sets and not the mapping `SERVICE_SERIES`, which holds a series name and a kind only.
- Precondition of `src/devops_cli/k8s/cluster_job_api.py:def create`: a client of the Kubernetes API; the cases of groups 2 and 3 give a fake Kubernetes client, so no case reaches the cluster.
- Precondition of `src/devops_cli/roadmap/job_launcher.py:def launch`: a client of the Kubernetes API; group 3 gives a fake Kubernetes client.
- Precondition of `src/devops_cli/roadmap/stage/stage_submit.py:def run_stage_round`: a checkout of the repository; the case of group 2 gives a clone under a temporary folder.
- Precondition of `src/devops_cli/roadmap/implement/implement_submit.py:def run_implement_round`: a checkout of the repository; the case of group 3 gives a clone under a temporary folder.
- The check of the exported Job keys is a module of the `k8s` row: `tests/gate/runner.py:def _check_modules` imports every module of the `k8s_checks` package and calls each function named `check_*`, as `tests/gate/k8s_checks/monitoring.py:def check_no_plain_service_sits_in_a_helm_namespace_without_owned_exemption` shows, so the new module joins the row with no registry file. `list_files` of `tests/gate/k8s_checks` listed 24 modules and no `dashboard_job_keys.py`, so group 6 creates it.
- Group 4 now names the file it changes in a code span: `read_file` of `k8s/monitoring/k8s-monitoring-values.yaml` confirmed the two anchors of the edit at lines 65 and 275, and the task text of group 4 writes the path `k8s/monitoring/k8s-monitoring-values.yaml` as a code span, so the step packs the file that it changes.
- Runner capability: each verify starts `uv run devops`, which the runner image holds; the test commands run `pytest`, and the `k8s` row runs `kubectl`, both in the runner tools. No program of this plan is NOT_IN_RUNNER. The pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault` stay as they are. The new check exits 1 with a message that names the panel title and the key.
- First checks against the real system, in the order of the work: `uv run devops ci test tests/telemetry/test_service_counter_series.py`, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_submit.py`, `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py`, `uv run devops ci --check --only k8s`, `uv run devops ci test tests/grafana/test_service_dashboard.py` and `uv run devops ci docs`.
- Criteria 1, 2 and 4 need the cluster and only a person runs them after the merge: the jsonpath of the Job of criterion 1, the two PromQL queries of criterion 2 and a Job row selected in the deployed dashboard for criterion 4. A test doubles only process edges, so no test reaches the cluster or Loki.

## Existing Tool Considered

kube-state-metrics, in use, covers the export of the Job labels, annotations and status series through its label and annotation allowlists and its keep list, and Grafana and Loki, both in use, draw the table and the log panel. The change builds its own panel template code instead of a tool: about 150 lines of template code and 4 cases, an estimated 60k tokens and half a day (4 hours) to build, keep and fix. It deletes no internal code.

## Dependencies

None.
