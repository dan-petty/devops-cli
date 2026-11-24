# Proposal

## Why

The logs, the metrics and the traces of the roadmap Service name a repository in different ways: Loki has no `repo` stream label for a unit pod, the router's delivery line carries the GitHub spelling of the repository, traces use `service.repo`, and the `repo` label of a Service metric keeps the spelling of `service.repos`. One Grafana variable cannot filter the three signals for one repository with one value (#4576).

## What Changes

- Add `src/devops_cli/telemetry/repo_context.py` with `current_repo`, `repo_scope` and `RepoContextFilter`, and export the three names from `src/devops_cli/telemetry/__init__.py`.
- Attach `RepoContextFilter` to the `json` handler of `service_log_config` in `src/devops_cli/server/json_logs.py`, beside the trace filter.
- Write the router's delivery record inside `repo_scope` in `src/devops_cli/server/routes/webhooks.py`, so the record holds the casefolded key of the delivery's repository and not the GitHub spelling.
- Set the repository scope around each round of `RepoWorker` in `src/devops_cli/server/service.py`, and give the `service.job` span and the `service.scoped` span the OpenTelemetry VCS attributes in place of `service.repo`.
- Hold `service.repos` as casefolded `RepoRef` keys in `ServiceManager`, prime the Service counters from that set, give a `RepoWorker` round the key or `other` through `RepoRef.metric_value`, and give the two `repo` labels of the webhook route the casefolded key.
- Map the pod annotation `roadmap.devops-cli/repository` to the Loki stream label `repo` under `podLogsViaLoki` in `k8s/monitoring/k8s-monitoring-values.yaml`, and hold the mapping in `tests/core/test_third_party_telemetry.py`.
- Add `check_the_router_deployment_carries_no_repository_annotation` to `tests/gate/k8s_checks/roadmap_service.py`, so the `k8s` row fails when the router Deployment `roadmap-service` carries the repository annotation.
- Document the repository value of the logs, the metrics and the traces in `docs/TELEMETRY.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-logs`: A Service log line names the repository of its work
- `repository-names`: A round span names its repository with the VCS attributes, A Service metric names its repository by the casefolded key
- `monitoring-collectors`: The k8s-monitoring values map the pod annotation to the repo stream label, The router pod keeps its stream labels

## Impact

- Code: `src/devops_cli/telemetry/repo_context.py`, `src/devops_cli/telemetry/__init__.py`, `src/devops_cli/server/json_logs.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/server/service.py`, `k8s/monitoring/k8s-monitoring-values.yaml`
- Documents: `docs/TELEMETRY.md`
- Tests: `tests/telemetry/test_repo_context.py`, `tests/server/test_service_log_trace_ids.py`, `tests/server/test_server_service.py`, `tests/telemetry/test_service_counter_series.py`, `tests/core/test_third_party_telemetry.py`, `tests/gate/k8s_checks/roadmap_service.py`

## Feasibility

- The probe says "The path `src/devops_cli/telemetry/logging_bridge.py` is a file of the staging commit.", and the module holds the filter that the issue names as the pattern of the change: `class TraceCorrelationFilter(logging.Filter):` and `def filter(self, record: logging.LogRecord) -> bool:`.
- The probe says "The path `service.repo` is no file of the staging commit. No commit in the history deleted or renamed it.", so `service.repo` is a span attribute and not a path; the plan replaces it on the round spans of `src/devops_cli/server/service.py`, where `src/devops_cli/server/service.py:684:"service.repo": self.repo,` sits, with the VCS attributes.
- `read_file` on `src/devops_cli/server/json_logs.py` shows `src/devops_cli/server/json_logs.py:93:"filters": {"trace": {"()": TraceCorrelationFilter}},` and `src/devops_cli/server/json_logs.py:95:"json": {"class": JsonLogStreamHandler, "formatter": "json", "filters": ["trace"]}`, so one filter entry and one handler list take the repository filter, and the entry line reads `"filters": {"trace": {"()": TraceCorrelationFilter}},`.
- `read_file` on `src/devops_cli/server/json_logs.py` shows `src/devops_cli/server/json_logs.py:14:CONTEXT_LOG_KEYS: Final[tuple[str, ...]] = (` with `repo` as its first key, so the formatter writes a `repo` attribute of a record, and `src/devops_cli/server/json_logs.py:84:name: {"handlers": ["json"], "level": numeric_level, "propagate": False}` shows that the `devops_cli` logger does not propagate, so a filter on the root logger would miss its records.
- `read_file` on `src/devops_cli/server/routes/webhooks.py` shows `src/devops_cli/server/routes/webhooks.py:467:"repo": self.repo,` inside `src/devops_cli/server/routes/webhooks.py:452:def conclude(self, outcome: str) -> None:`, so the delivery record already writes `repo` with the GitHub spelling, and the gap of the issue is the casefolded key.
- `read_file` on `src/devops_cli/github/repo_ref.py` shows the staged constants and methods that the plan relies on: `src/devops_cli/github/repo_ref.py:36:OTHER_REPOSITORY: Final[str] = "other"`, `src/devops_cli/github/repo_ref.py:217:def metric_value(self, configured: Collection[RepoRef]) -> str:`, `src/devops_cli/github/repo_ref.py:220:return self.key if self in configured else OTHER_REPOSITORY` and `src/devops_cli/github/repo_ref.py:223:def span_attributes(self) -> dict[str, str]:`, and the module holds `OTHER_REPOSITORY: Final[str] = "other"` and `def metric_value(self, configured: Collection[RepoRef]) -> str:`.
- `search_code` for `roadmap.devops-cli/repository` shows `src/devops_cli/k8s/cluster_job.py:52:REPOSITORY_ANNOTATION = "roadmap.devops-cli/repository"`, and `references` on that name answers 9 files and 12 lines, none of them under `k8s/`, so the count of committed manifests that carry the annotation is 0 and the router Deployment carries none today.
- `read_file` on `k8s/monitoring/k8s-monitoring-values.yaml` shows `k8s/monitoring/k8s-monitoring-values.yaml:119:podLogsViaLoki:` with `enabled: true` and `collector: alloy-logs`, the block that takes the annotation mapping.
- `read_file` on `k8s/devops/roadmap-service/deployment.yaml` shows `k8s/devops/roadmap-service/deployment.yaml:4:name: roadmap-service` and `k8s/devops/roadmap-service/deployment.yaml:37:annotations:`, the pod template annotation map that group 7 asserts holds no repository annotation.
- `read_file` on `tests/gate/k8s_checks/roadmap_service.py` shows `tests/gate/k8s_checks/roadmap_service.py:45:rendered = applied_documents(K8S_DIR / "overlays" / "homelab" / "devops")`, so a check of the `k8s` row renders the router Deployment from the checkout, and `tests/gate/charts_render.py:37:def chart_objects(application: Path) -> tuple[dict[str, Any], ...]:` shows that the `charts` row renders the chart source of an Argo CD Application with its values files.
- The finding on the unit-pod scenario is answered: its `then` is now the mapping in `k8s/monitoring/k8s-monitoring-values.yaml`, which the test that group 6 extends asserts through `tests/core/test_third_party_telemetry.py:53:values_path = K8S_DIR / "monitoring" / "k8s-monitoring-values.yaml"`, and the live Loki query is gone from the spec.
- The finding on the router scenario is answered: its `then` is a property of the render of `k8s/devops/roadmap-service/deployment.yaml`, and group 7 adds `check_the_router_deployment_carries_no_repository_annotation` to `tests/gate/k8s_checks/roadmap_service.py`, which the `k8s` row runs, so a test asserts the result and the live `kubectl` command is gone.
- `docs/TESTING.md` holds the manifest rule of this plan: a scenario of a manifest change names a validator command or a live check, and it names `uv run devops ci --check --only k8s` and `uv run devops ci --check --only charts`; each new scenario of `monitoring-collectors` names one of them in its `when`, and no `verify` of a group names the `charts` row, whose `helm` and `docker` are `NOT_IN_RUNNER`.
- `applied_documents(path)` needs a checkout of the repository as a precondition of the call: it reads the manifest files under `k8s/` and runs `kubectl kustomize` on them, and it needs no client of a service and no network.
- No other function that the plan calls needs a checkout, a client or a network: `RepoRef`, `RepoRef.metric_value`, `RepoRef.span_attributes`, `repo_scope` and `RepoContextFilter` read and set values in memory, and the class `RepoRef` holds `return self.display.casefold()` as its `key` property.
- Each verify runs `uv`, `devops`, `python` and `pytest` from the runner image with the failure class `test`, and `uv run devops ci --check --only k8s` also runs `kubectl` from the image; no program of the plan is `NOT_IN_RUNNER`, and the pod settings that apply are readOnlyRootFilesystem: true, runAsNonRoot: true, allowPrivilegeEscalation: false, capabilities.drop: ALL and seccompProfile: RuntimeDefault.
- The first checks that the implementation runs against the real system are `uv run devops ci test tests/telemetry/test_repo_context.py`, `uv run devops ci test tests/server/test_service_log_trace_ids.py`, `uv run devops ci test tests/server/test_server_service.py`, `uv run devops ci test tests/telemetry/test_service_counter_series.py`, `uv run devops ci test tests/core/test_third_party_telemetry.py`, `uv run devops ci --check --only k8s` and `uv run devops ci docs`; each runs offline from the image with no network, no cluster and no model call.
- The capability `monitoring-collectors` exists and holds no requirement for the `repo` stream label, so its two requirements are `added`, and the living spec `workload-resource-limits` shows the `uv run devops ci --check --only charts` form of a values-file proof.

## Existing Tool Considered

OpenTelemetry semantic conventions (Apache-2.0) cover the VCS span attributes, and the grafana/k8s-monitoring chart covers the Loki pod-annotation stream label. The project writes the log-record filter, the context variable and the bounded metric label itself: about 200,000 tokens and 2 hours to build, about 5,000 tokens a month to keep, and about 20,000 tokens to fix. The change deletes no internal code.

## Dependencies

- #4558: it writes the pod annotation `roadmap.devops-cli/repository` from `RepoRef.key` on the Service Job and the pod template of a repository's unit of work, and that annotation is the one this change maps to the `repo` stream label, so it comes first.
- #4533: it added `src/devops_cli/github/repo_ref.py` with the casefolded `key` that this change writes into the logs, the metrics and the traces, so it comes first.
