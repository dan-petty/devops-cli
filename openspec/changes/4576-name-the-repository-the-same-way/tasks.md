# Tasks

## 1. Hold the repository of the work and copy it onto each record

Kind: behavior. Reads: `src/devops_cli/telemetry/logging_bridge.py`, `src/devops_cli/telemetry/__init__.py`, `src/devops_cli/github/repo_ref.py`, `tests/telemetry/test_telemetry_logging_bridge.py`, `tests/telemetry/test_telemetry.py`. Changes: `src/devops_cli/telemetry/repo_context.py` (new), `src/devops_cli/telemetry/__init__.py`, `tests/telemetry/test_repo_context.py` (new).
Adds: `RepoContextFilter`, `current_repo`, `repo_scope`

- [ ] 1.1 Add `test_a_record_carries_the_casefolded_key_of_the_current_repository` and `test_a_record_outside_a_scope_keeps_no_repo_key` to `tests/telemetry/test_repo_context.py`; both fail on the base, because `src/devops_cli/telemetry/repo_context.py` does not exist, and they assert that `RepoContextFilter` sets `repo` to `example-org/repo1` inside `repo_scope("Example-Org/Repo1")` and leaves a record that carries no `repo` alone outside every scope
  - Verification: `$ uv run devops ci test tests/telemetry/test_repo_context.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/telemetry/repo_context.py` after the shape of `src/devops_cli/telemetry/logging_bridge.py`. It holds a `ContextVar` of a `RepoRef` or `None`, `current_repo()` that reads it, `repo_scope(repo: str | None)`, a context manager that sets the reference from `RepoRef(repo)` when `repo` is not None and clears it otherwise, and `RepoContextFilter(logging.Filter)`, whose `filter` sets `record.repo` to the casefolded key of the current reference, replacing a value the record carries, and returns True; with no current reference it changes nothing. Add the three names to the lazy export table of `src/devops_cli/telemetry/__init__.py`
  - Verification: `$ uv run devops ci test tests/telemetry/test_repo_context.py` passes

## 2. Attach the repository filter to the Service json handler

Kind: behavior. Reads: `src/devops_cli/server/json_logs.py`, `src/devops_cli/telemetry/repo_context.py`, `tests/server/test_service_log_trace_ids.py`, `tests/roadmap/test_job_grade_report.py`, `tests/server/test_server.py`, `tests/server/test_server_service.py`. Changes: `src/devops_cli/server/json_logs.py`, `tests/server/test_service_log_trace_ids.py`.

- [ ] 2.1 Add `test_the_json_handler_carries_the_repository_filter` to `tests/server/test_service_log_trace_ids.py`; it fails on the base, because `service_log_config` in `src/devops_cli/server/json_logs.py` names no repository filter, and it asserts that the `filters` block holds it beside `trace`, that the `json` handler lists both, and that a record formatted through that config holds `repo` with the casefolded key of the current reference
  - Verification: `$ uv run devops ci test tests/server/test_service_log_trace_ids.py` fails on the base
- [ ] 2.2 In `src/devops_cli/server/json_logs.py`, import `RepoContextFilter` from `devops_cli.telemetry.repo_context`, add it to the `filters` block of `service_log_config` beside `trace`, and add its name to the `filters` list of the `json` handler. Say in the docstring of `service_log_config` that the repository filter puts the casefolded repository of the current work on each record the handler gets
  - Verification: `$ uv run devops ci test tests/server/test_service_log_trace_ids.py` passes

## 3. Name the repository on each router delivery record

Kind: behavior. Reads: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/telemetry/repo_context.py`, `tests/server/test_server_service.py`, `tests/server/test_service_log_trace_ids.py`, `tests/models/test_webhooks.py`, `tests/server/routes/test_k8s_roadmap_service.py`, `tests/server/routes/test_roadmap_consumer_comment_events.py`, `tests/server/routes/test_roadmap_consumer_pull_events.py`, `tests/server/test_mattermost_slash_command.py`, `tests/telemetry/test_service_counter_series.py`. Changes: `src/devops_cli/server/routes/webhooks.py`, `tests/server/test_server_service.py`.

- [ ] 3.1 Add `test_a_router_delivery_record_names_the_casefolded_repository_key` to `tests/server/test_server_service.py`; it fails on the base, because the record that `_Delivery.conclude` in `src/devops_cli/server/routes/webhooks.py` writes for a signed delivery of `Example-Org/Repo1` carries the GitHub spelling, and it asserts that the formatted JSON line holds `repo` with `example-org/repo1`
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py` fails on the base
- [ ] 3.2 In `src/devops_cli/server/routes/webhooks.py`, import `repo_scope` from `devops_cli.telemetry.repo_context` and write the record of `_Delivery.conclude` inside `with repo_scope(self.repo):`, so the filter replaces the record's `repo` with the casefolded key; a refused delivery names no repository, so `repo_scope(None)` leaves the record unchanged. In `tests/server/test_server_service.py`, install the `json` handler of `service_log_config` through `logging.config.dictConfig` as the `service_logger` fixture of `tests/server/test_service_log_trace_ids.py` does, post a signed delivery whose `repository.full_name` is `Example-Org/Repo1`, and assert that the line from `capsys` holds `repo` with `example-org/repo1`
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py` passes

## 4. Name the repository in each round record and each round span

Kind: behavior. Reads: `src/devops_cli/server/service.py`, `src/devops_cli/github/repo_ref.py`, `src/devops_cli/telemetry/repo_context.py`, `tests/server/test_server_service.py`, `tests/github/test_github_app_identity.py`, `tests/github/test_service_limits.py`, `tests/roadmap/test_roadmap_run_errors.py`, `tests/roadmap/test_roadmap_run_lanes.py`, `tests/roadmap/test_roadmap_run_request_rows.py`, `tests/roadmap/test_roadmap_run_service.py`, `tests/roadmap/test_roadmap_run_state_faults.py`, `tests/server/test_mattermost_slash_command.py`, `tests/server/test_server.py`, `tests/server/test_service_manager.py`, `tests/server/test_service_memory.py`, `tests/server/test_service_rows_lease.py`, `tests/server/test_service_state_unkept.py`, `tests/telemetry/test_service_counter_series.py`, `tests/telemetry/test_telemetry_metrics.py`. Changes: `src/devops_cli/server/service.py`, `tests/server/test_server_service.py`.

- [ ] 4.1 Add `test_a_round_record_names_its_repository` and `test_a_round_span_names_its_repository` to `tests/server/test_server_service.py`; both fail on the base, because a round of `RepoWorker` in `src/devops_cli/server/service.py` writes `service.repo` on its span and no `repo` on its record, and they assert that the record holds `repo` with the casefolded key and that the span holds the three VCS attributes and no `service.repo`
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py` fails on the base
- [ ] 4.2 In `src/devops_cli/server/service.py`, wrap the body of `RepoWorker._execute_batch` and of `RepoWorker._execute_scoped` in `repo_scope(self.repo)`, so each record written in the round carries the casefolded key. Build the attributes of the `service.job` span and of the `service.scoped` span from `RepoRef(self.repo).span_attributes` plus `service.lane` and the trigger attributes of that span, and delete both `service.repo` entries. In `tests/server/test_server_service.py`, change the two assertions on `service.repo` to the three VCS attributes
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py` passes

## 5. Label each Service metric with the casefolded repository key

Kind: behavior. Reads: `src/devops_cli/server/service.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/server/counter_series.py`, `src/devops_cli/github/repo_ref.py`, `tests/telemetry/test_service_counter_series.py`, `tests/server/test_service_manager.py`, `tests/github/test_github_app_identity.py`, `tests/github/test_service_limits.py`, `tests/models/test_webhooks.py`, `tests/roadmap/test_roadmap_run_errors.py`, `tests/roadmap/test_roadmap_run_lanes.py`, `tests/roadmap/test_roadmap_run_request_rows.py`, `tests/roadmap/test_roadmap_run_service.py`, `tests/roadmap/test_roadmap_run_state_faults.py`, `tests/server/routes/test_k8s_roadmap_service.py`, `tests/server/routes/test_roadmap_consumer_comment_events.py`, `tests/server/routes/test_roadmap_consumer_pull_events.py`, `tests/server/test_mattermost_slash_command.py`, `tests/server/test_server.py`, `tests/server/test_server_service.py`, `tests/server/test_service_memory.py`, `tests/server/test_service_rows_lease.py`, `tests/server/test_service_state_unkept.py`, `tests/telemetry/test_telemetry_metrics.py`. Changes: `src/devops_cli/server/service.py`, `src/devops_cli/server/routes/webhooks.py`, `tests/telemetry/test_service_counter_series.py`.

- [ ] 5.1 Add `test_the_repo_label_of_a_configured_repository_is_its_casefolded_key` and `test_a_worker_of_a_repository_outside_service_repos_counts_under_other` to `tests/telemetry/test_service_counter_series.py`; both fail on the base, because the primed labels keep the spelling of `service.repos` and a `RepoWorker` labels every round with its own name, and they assert that a manager of `Example-Org/Repo1` primes `example-org/repo1` and that a worker of `example/outside` counts its round under `other`
  - Verification: `$ uv run devops ci test tests/telemetry/test_service_counter_series.py` fails on the base
- [ ] 5.2 In `src/devops_cli/server/service.py`, set `managed_repos` to the set of `RepoRef(repo).key` of `config.repos`, build the workers from that set and prime the counters with it, so no metric label carries the GitHub spelling. Give `RepoWorker` the keyword `configured` of the `RepoRef` values of `service.repos`, defaulting to the worker's own repository, and set the `repo` value of `_labels` with `RepoRef(self.repo).metric_value(configured)`. In `src/devops_cli/server/routes/webhooks.py`, compare a delivery's repository and the chat target by `RepoRef(...).key` against `managed_repos`, and give the two `repo` labels of a delivery the casefolded key
  - Verification: `$ uv run devops ci test tests/telemetry/test_service_counter_series.py` passes

## 6. Map the pod annotation to the repo stream label

Kind: other. Reads: `k8s/monitoring/k8s-monitoring-values.yaml`, `src/devops_cli/k8s/cluster_job.py`, `tests/core/test_third_party_telemetry.py`. Changes: `k8s/monitoring/k8s-monitoring-values.yaml`, `tests/core/test_third_party_telemetry.py`.

- [ ] 6.1 Under `podLogsViaLoki` in `k8s/monitoring/k8s-monitoring-values.yaml`, add `annotations: {roadmap.devops-cli/repository: repo}`: the annotation name that `REPOSITORY_ANNOTATION` in `src/devops_cli/k8s/cluster_job.py` writes on a unit pod is the key, and the Loki label name is the value. Add a comment that the chart renames the annotation into the label `repo` and that only a unit pod carries it. Leave the router manifests unchanged, and extend the assertion of `tests/core/test_third_party_telemetry.py` on that values file with the mapping, so a test asserts the values entry
  - Verification: `$ uv run devops ci test tests/core/test_third_party_telemetry.py` passes

## 7. Assert the router deployment carries no repository annotation

Kind: other. Reads: `tests/gate/k8s_checks/roadmap_service.py`, `k8s/devops/roadmap-service/deployment.yaml`, `tests/gate/k8s_render.py`, `src/devops_cli/k8s/cluster_job.py`. Changes: `tests/gate/k8s_checks/roadmap_service.py`.

- [ ] 7.1 Add `check_the_router_deployment_carries_no_repository_annotation` to `tests/gate/k8s_checks/roadmap_service.py`: it renders `k8s/overlays/homelab/devops` with `applied_documents`, as the checks beside it do, takes the Deployment `roadmap-service` of namespace `devops`, and asserts that its pod template metadata carries no `roadmap.devops-cli/repository` annotation, so the router pod gets no `repo` stream label from the k8s-monitoring chart. Name the key from `REPOSITORY_ANNOTATION` in `src/devops_cli/k8s/cluster_job.py`, so the check and the builder name one annotation
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 8. Document the repository value of the three signals

Kind: other. Reads: `docs/TELEMETRY.md`, `src/devops_cli/github/repo_ref.py`. Changes: `docs/TELEMETRY.md`.

- [ ] 8.1 Document in `docs/TELEMETRY.md` that the Service writes `repo` with the casefolded `owner/name` into each JSON line of a repository's work, that a round span carries `vcs.provider.name`, `vcs.owner.name` and `vcs.repository.name` and no `service.repo`, that the `repo` label of a Service metric is the casefolded key or `other`, and that a unit pod carries the `repo` stream label from its `roadmap.devops-cli/repository` annotation while the router pod keeps its stream labels
  - Verification: `$ uv run devops ci docs` passes
- [ ] 8.2 Edit `docs/TELEMETRY.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: `{service_name="roadmap-service"} | json | repo="<owner>/<name>"` returns lines from each repository's work.
- Group 6: `{repo="<owner>/<name>"}` returns the lines of a unit pod, and the value is the casefolded `key` in logs, metrics and traces.
- Group 4: TraceQL `{span.vcs.repository.name="<name>"}` finds round spans.
- Group 5: `count by (repo)` over `devops_cli_service_*` gives only `service.repos` values and `other`.
- Group 7: The router pod gets no new stream label.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
