# Proposal

## Why

Pod `tempo-0` in namespace `otel` stopped with `OOMKilled` twice on 2026-11-21, at 07:07 and 07:08:31 UTC, at the limit of `k8s/otel/tempo-values.yaml:39:memory: 2048Mi`, because the values set no limit on a search and no limit on the size of a trace: ten reads of the search API could hold the memory of the container, so a person could not read a trace while the pod restarted and the pod kept no span of that window (#6616).

## What Changes

- Add the `queryFrontend` and `querier` blocks under `tempo:` in `k8s/otel/tempo-values.yaml`: `search.max_bytes_per_trace` `1000000`, `search.max_result_limit` `50`, `search.max_duration` `30s`, `search.target_bytes_per_second` `25000000`, `max_outstanding_per_tenant` `10` and `querier.max_concurrent_queries` `4`, with a comment that names #6616 and the memory bound.
- Add `global_overrides.max_bytes_per_trace` `1000000` under `tempo:`, so Tempo discards the spans of a trace beyond that size as it receives the trace; a trace that the store already holds can be larger and stays readable for the retention of `168h`, and the concurrency limit bounds how many reads hold memory at once.
- Keep the limit at `k8s/otel/tempo-values.yaml:39:memory: 2048Mi` and the retention at `k8s/otel/tempo-values.yaml:32:retention: 168h`, and leave the `securityContext`, `persistence` and `affinity` blocks as they are.
- Create `tests/gate/k8s_checks/tempo_query_limits.py` with `check_the_tempo_query_limits_stay_under_the_memory_limit`, which the `k8s` row runs with no registration; it reads the values with `yaml.safe_load`, reads the memory limit with `parse_quantity`, and asserts the seven values, the `2048Mi` limit and the two products under half of the limit.
- Carry the spec delta of `workload-resource-limits`, because a Helm values file is a manifest and its limits are behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `workload-resource-limits`: The Tempo query limits stay under the memory limit

## Impact

- Code: `k8s/otel/tempo-values.yaml`
- Tests: `tests/gate/k8s_checks/tempo_query_limits.py`

## Feasibility

- The probe lines confirm the file that the issue cites, word for word: "The path `k8s/otel/tempo-values.yaml` is a file of the staging commit." and "The path `query_frontend.search.max_bytes_per_trace` is no file of the staging commit. No commit in the history deleted or renamed it.", so the limits are things that the change creates, and not a path that a commit removed.
- read_file `k8s/otel/tempo-values.yaml` showed the constant that the plan keeps, `k8s/otel/tempo-values.yaml:39:memory: 2048Mi`, and the retention `k8s/otel/tempo-values.yaml:32:retention: 168h`, with no query limit: the `tempo:` block of lines 24 to 39 holds `securityContext`, `reportingEnabled`, `retention` and `resources` only.
- search_code `max_outstanding_per_tenant`, search_code `queryFrontend` and search_code `global_overrides` each returned `No match.`, so no file of the repository holds one of those keys yet, and list_files `tests/gate/k8s_checks` showed 21 modules, none of which reads the Tempo values.
- git_show f209f6c8 on `k8s/otel/tempo-values.yaml` shows the `config:` override that #1813 removed, and its body rendered `query_frontend` from `.Values.tempo.queryFrontend`, `querier` from `.Values.tempo.querier` and `overrides` from `.Values.tempo.global_overrides`; the chart's own template is no file of this repository, so this run did not read the chart's mapping, and the first live check below proves it.
- `tests/gate/k8s.py:17:return run_checks("k8s", k8s_checks)` runs the modules of the package, `tests/gate/runner.py:32:def _check_modules(package: ModuleType) -> list[ModuleType]:` imports each one, and `tests/gate/runner.py:45:if name.startswith("check_") and function.__module__ == module.__name__` selects each function named `check_`, so a new module joins the `k8s` row with no registration.
- `src/devops_cli/commands/ci.py:1126:cmd=_python_check_cmd("k8s"),` and the option at `src/devops_cli/commands/ci.py:1781:"--only",` give the verify command `uv run devops ci --check --only k8s`, the row that fails when the new check fails.
- `tests/gate/k8s_checks/telemetry_resource.py:23:MONITORING_VALUES = REPO_ROOT / "k8s" / "monitoring" / "k8s-monitoring-values.yaml"` and `tests/gate/k8s_checks/telemetry_resource.py:66:monitoring = yaml.safe_load(MONITORING_VALUES.read_text(encoding="utf-8"))` give the shape of a gate check that reads a chart values file, and `tests/support/paths.py:21:REPO_ROOT: Final[Path] = TESTS_ROOT.parent` gives its root.
- `tests/gate/k8s_checks/runner.py:10:from kubernetes.utils.quantity import parse_quantity` shows that the gate already reads a Kubernetes quantity with the client library, so the new check reads `2048Mi` with `parse_quantity` and parses no suffix by hand.
- `tests/gate/tree_checks/config_values.py:78:_SKIPPED_PARTS: Final[frozenset[str]] = frozenset({"support", "fixtures", "golden", "gate"})` exempts the gate from the count of tests that read a committed config file, so the check of the `k8s` row is the validator of the values file and the change adds no pytest module that asserts a value of it.
- `k8s/argocd/apps/tempo.yaml:13:targetRevision: 3.2.1` pins chart `tempo`, `k8s/argocd/apps/tempo.yaml:16:- $values/k8s/otel/tempo-values.yaml` gives the chart this values file, and `src/devops_cli/commands/k8s/stack_lifecycle.py:208:"values": ["otel/tempo-values.yaml"],` gives the same path to the `tempo` release of the stack, and all three stay unchanged.
- The reproduction of the issue and the rendered Tempo configuration are `not checked` in this run: this run read files and searched the tree only, opened no client of the cluster and sent no request to the Tempo API. The implementation runs the two live checks below, and each of them needs a client of the cluster and a network.
- The implementation runs the first live check as `kubectl -n otel get configmap -l app.kubernetes.io/name=tempo -o yaml`, and its output must show `max_bytes_per_trace: 1000000`, `max_result_limit: 50`, `max_duration: 30s`, `target_bytes_per_second: 25000000`, `max_outstanding_per_tenant: 10` and `max_concurrent_queries: 4`, which shows that the chart renders the keys that the change sets.
- The implementation runs the second live check as the reproduction: `kubectl -n otel port-forward svc/tempo 13200:3200`, then ten `GET /api/search?q={name="invoke_agent agent"}&start=<t-900>&end=<t+120>&limit=50&spss=20` requests over the busy hour, and it sends one `GET /api/traces/<id>` request for each trace that a search returns; it takes the restart count of pod `tempo-0` with `kubectl -n otel get pod tempo-0 -o jsonpath='{.status.containerStatuses[0].restartCount}'` before and after, and it expects no increase, because the issue records "The restart count went to 2."
- A trace that the store holds before the change can be larger than `1000000` bytes and stays available for the retention of `168h`; the change bounds how many reads hold memory at once with `querier.max_concurrent_queries` of `4` and `10` outstanding queries per tenant, and the second live check measures the pod in that state.
- The check calls `Path.read_text` on `k8s/otel/tempo-values.yaml`, whose argument is a path of the repository: that call needs a checkout of the repository, and no client of a service and no network. `yaml.safe_load` and `parse_quantity` need no checkout, no client and no network.
- The plan introduces no new program. The verify program `uv run devops ci --check --only k8s` runs `uv`, `devops`, `python3` and the `kubectl` that the `k8s` row renders with, which the runner tools list names; it lists `helm` under `NOT_IN_RUNNER`, and the plan needs no `helm`, because the check reads the values file and Argo CD renders the chart on the cluster.
- A failed row stops the step with the class `test`, whose action is `repair`. The check writes no file, so the pod settings `readOnlyRootFilesystem: true`, `capabilities.drop: ALL`, `runAsNonRoot: true` and `seccompProfile: RuntimeDefault` need no change.
- The issue can be built as written: the file that it cites is at the staging commit, the limit that it names is the `2048Mi` of line 39, `queryFrontend`, `querier` and `global_overrides` are the three keys that the removed override rendered, and the `k8s` row is the validator of the file.
- The probe lines also say, word for word: "Not probed, the bound of 10 commands is reached: `querier.max_concurrent_queries`, `tempo.config`, `and.proposal`, `otel`, `OOMKilled`, `max_bytes_per_trace`, `Running`, `max_result_limit`, `max_duration`, `target_bytes_per_second`, `config`", and this run checked the names it needed with its own search calls above.

## Existing Tool Considered

Grafana Tempo (grafana/tempo, AGPL-3.0, maintained, last activity 2026-11-21), which the project already runs as its trace backend and which ships the search byte, result, duration and byte-rate limits, the outstanding-query limit per tenant, the querier concurrency limit and the per-tenant trace size limit that the change sets in the chart values. The change builds no replacement code and deletes no internal code, so it has no cost to build or keep.

## Dependencies

None.
