# Tasks

## 1. Guard the Service series against an unbounded Job value

Kind: other. Reads: `src/devops_cli/server/counter_series.py`, `src/devops_cli/telemetry/metrics.py`, `tests/telemetry/test_service_counter_series.py`. Changes: `tests/telemetry/test_service_counter_series.py`.

- [ ] 1.1 Add the case `test_no_service_series_carries_an_item_branch_or_worktree_label` to `tests/telemetry/test_service_counter_series.py`, after its `tests/telemetry/test_service_counter_series.py:def _series` helper: it starts `_manager(REPOS)`, which primes the Service counters through `src/devops_cli/server/counter_series.py:def prime_service_counters`, then walks each sample of `GLOBAL_METRICS.registry.collect()` and asserts that no label key is item, branch or worktree. It also asserts that the walk saw a sample of `CONST_SERVICE_METRIC_JOBS`, so an empty registry cannot pass the case
  - Verification: `$ uv run devops ci test tests/telemetry/test_service_counter_series.py` passes

## 2. Set the branch and the lane clone on the stage Job

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_job.py`, `src/devops_cli/roadmap/stage/stage_submit.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_submit.py`, `tests/k8s/test_k8s_cluster_job.py`, `tests/k8s/test_k8s_cluster_job_api.py`, `tests/commands/k8s/test_k8s_run_job.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/test_roadmap_step_fix_checks.py`, `tests/github/test_repo_ref.py`, `tests/roadmap/implement/test_roadmap_implement_deadline.py`, `tests/roadmap/implement/test_roadmap_implement_outside.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/test_roadmap_closed_plan_webhook.py`, `tests/roadmap/test_roadmap_fix_checks_row.py`, `tests/roadmap/test_roadmap_phase.py`, `tests/roadmap/test_roadmap_release_roll.py`, `tests/roadmap/test_roadmap_run_job.py`, `tests/roadmap/test_roadmap_watch_row.py`, `tests/server/test_server_infra_apply.py`, `tests/server/test_server_infra_plan.py`. Changes: `src/devops_cli/k8s/cluster_job.py`, `src/devops_cli/roadmap/stage/stage_submit.py`, `tests/roadmap/stage/test_roadmap_stage_submit.py`.
Adds: `BRANCH_ANNOTATION`, `WORKTREE_ANNOTATION`, `stage_job_annotations`

- [ ] 2.1 the case `test_the_stage_job_carries_its_branch_and_lane_clone` in `tests/roadmap/stage/test_roadmap_stage_submit.py`, which runs the stage round in a clone under `tmp_path` with a fake Kubernetes client and fails until the created Job holds the two annotations
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_submit.py` fails on the base
- [ ] 2.2 Add `BRANCH_ANNOTATION`, `WORKTREE_ANNOTATION` and `stage_job_annotations` to `src/devops_cli/k8s/cluster_job.py` beside `REPOSITORY_ANNOTATION`. In `src/devops_cli/roadmap/stage/stage_submit.py` pass the target and the clone of the round into `_submit`, and give its create call at `src/devops_cli/roadmap/stage/stage_submit.py:329:labels=stage_job_labels(ref, item.number),` the keyword `annotations=stage_job_annotations(target.branch, str(source))`, so the Job and its pod template carry the branch and the clone path of the lane
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_submit.py` passes

## 3. Set the branch and the lane clone on the implement Job

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_job.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/implement/implement.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`. Changes: `src/devops_cli/roadmap/implement/implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`.

- [ ] 3.1 the case `test_the_runner_job_carries_its_branch_and_lane_clone` in `tests/roadmap/implement/test_roadmap_implement_submit.py`, which runs the implement round in a clone under `tmp_path` with a fake Kubernetes client and fails until the created Job holds the two annotations
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py` fails on the base
- [ ] 3.2 Pass the clone of the round from `_submit_selected_targets` of `src/devops_cli/roadmap/implement/implement_submit.py` into `_create`, and add `BRANCH_ANNOTATION: target.branch` and `WORKTREE_ANNOTATION: str(source)` to the annotations mapping at `src/devops_cli/roadmap/implement/implement_submit.py:557:annotations={`, so the Job and its pod template carry the branch and the clone path of the lane
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py` passes

## 4. Keep and export the Job families and keys in the monitoring values

Kind: other. Reads: `k8s/monitoring/k8s-monitoring-values.yaml`. Changes: `k8s/monitoring/k8s-monitoring-values.yaml`.

- [ ] 4.1 Edit `k8s/monitoring/k8s-monitoring-values.yaml` only. Add `kube_job_labels`, `kube_job_annotations`, `kube_job_status_active`, `kube_job_status_start_time` and `kube_job_status_completion_time` to the keep list under `k8s/monitoring/k8s-monitoring-values.yaml:65:includeMetrics:`, because no kube_job family is there. Add the entry jobs=[roadmap.devops-cli/owner,roadmap.devops-cli/repo,roadmap.devops-cli/item,app.kubernetes.io/component] to `k8s/monitoring/k8s-monitoring-values.yaml:275:metricLabelsAllowlist:`, and add the key metricAnnotationsAllowlist with jobs=[roadmap.devops-cli/branch,roadmap.devops-cli/worktree]. Add a comment that names this issue, says that the two annotation values are bounded and hold no secret, and says that the series of a Job end with the Job
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 5. Build the Job panels and regenerate the Roadmap Service dashboard

Kind: behavior. Reads: `src/devops_cli/grafana/service_dashboard.py`, `src/devops_cli/grafana/service_specs.py`, `tests/grafana/test_service_dashboard.py`, `k8s/monitoring/dashboards/services.toml`, `Makefile`, `tests/commands/test_grafana.py`, `tests/grafana/test_service_specs.py`, `tests/prometheus/test_dashboard_queries.py`. Changes: `src/devops_cli/grafana/service_specs.py`, `src/devops_cli/grafana/service_dashboard.py`, `tests/grafana/test_service_dashboard.py`, `k8s/monitoring/dashboards/services.toml`, `k8s/monitoring/dashboards/devops-roadmap-service.json`.
Adds: `_job_variables`, `_jobs_row`, `_work_log`

- [ ] 5.1 the case `test_the_job_table_and_the_work_log_show_the_live_jobs` in `tests/grafana/test_service_dashboard.py`, which calls the builder with a spec whose `jobs` field is true and fails until the Service jobs table reads `kube_job_labels`, `kube_job_annotations` and `label_app_kubernetes_io_component` under the variables `$repo`, `$item` and `$job`, and the Work log panel queries the `loki` data source with `{namespace="devops"} | pod=~"$job.*"`
  - Verification: `$ uv run devops ci test tests/grafana/test_service_dashboard.py` fails on the base
- [ ] 5.2 Add `jobs: bool = False` to the spec of `src/devops_cli/grafana/service_specs.py`, in the shape of its `logs` field. In `src/devops_cli/grafana/service_dashboard.py` add `_job_variables`, `_jobs_row` and `_work_log` and call them from the builder when the spec's `jobs` field is true: the variables repo, item and job, a row Service jobs with the table panel, and the Work log panel. The table joins `kube_job_labels` with `kube_job_annotations` on the Job name, reads `kube_job_status_start_time` and `kube_job_status_completion_time`, links the item column to the issue and the branch column to the tree of the repository, and filters on `$repo`, `$item` and `$job`. The Work log panel queries `{namespace="devops"} | pod=~"$job.*"` on the Loki data source, in the shape of the stream selector of `src/devops_cli/grafana/service_dashboard.py:def _logs`. Set the `jobs` field to true in the `devops-roadmap-service` table of `k8s/monitoring/dashboards/services.toml` and run `make dashboards`
  - Verification: `$ uv run devops ci test tests/grafana/test_service_dashboard.py` passes

## 6. Check that the Job panels read only the exported keys

Kind: other. Reads: `tests/gate/k8s_checks/monitoring.py`, `tests/gate/runner.py`, `k8s/monitoring/k8s-monitoring-values.yaml`, `k8s/monitoring/dashboards/devops-roadmap-service.json`. Changes: `tests/gate/k8s_checks/dashboard_job_keys.py` (new).

- [ ] 6.1 Add the module `tests/gate/k8s_checks/dashboard_job_keys.py` with a `check_dashboard_job_keys` function, in the shape of `tests/gate/k8s_checks/monitoring.py`, so the row finds it with no registry file. It reads the Job label keys of `metricLabelsAllowlist` and the Job annotation keys of `metricAnnotationsAllowlist` for jobs from `k8s/monitoring/k8s-monitoring-values.yaml`, reads the kube-state-metrics keep list of `clusterMetrics.kube-state-metrics.metricsTuning.includeMetrics`, collects each kube_job metric name and each label_ and annotation_ selector of the PromQL of the panels of `k8s/monitoring/dashboards/devops-roadmap-service.json`, and asserts that the set of keys and families that no entry exports is empty, naming the panel title and the key in the assertion message
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 7. Document the Job panels, the annotations and the exported keys

Kind: other. Reads: `k8s/README.md`, `docs/DESIGN.md`. Changes: `k8s/README.md`, `docs/DESIGN.md`.

- [ ] 7.1 In `k8s/README.md`, add the Service jobs table and the Work log panel to the dashboard row, add the two Job annotations to the runner and stage Job sections, and add the jobs entries of the kube-state-metrics keep list and the two allowlists to the monitoring section. In `docs/DESIGN.md`, replace the row at `docs/DESIGN.md:259:| Service dashboard | The Grafana layout of` whose text says the dashboard holds all but the jobs table, which #3655 adds, with the panels that the template now builds
  - Verification: `$ uv run devops ci docs` passes
- [ ] 7.2 Edit `k8s/README.md` and `docs/DESIGN.md` for the Service jobs table, the Work log panel, the two Job annotations and the exported Job families and keys
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: `kubectl -n devops get jobs -o jsonpath` shows the branch and worktree annotations on a new runner Job and a new stage Job.
- Group 4: A PromQL query `kube_job_annotations{namespace="devops"}` returns the branch and worktree of a live Job, and `kube_job_labels` returns its repo and item.
- Group 6: The Service dashboard has a "Service jobs" table and a "Work log" panel. A dashboard test fails and names the panel when a query reads a metric or a label that is not exported (the rule of #3655).
- Pending person: Selecting a Job row shows that Job's Loki lines within 60 s of their write., Only a person on the deployed dashboard can select a Job row and see its lines arrive in Loki within 60 s; no test reaches the cluster or Loki.
- Group 1: No Service metric gains an item, branch or worktree label (a test checks the instruments).

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
