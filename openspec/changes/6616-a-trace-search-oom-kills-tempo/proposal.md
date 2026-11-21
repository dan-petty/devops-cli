# Proposal

## Why

Two reads of the Tempo HTTP API OOM-killed pod `tempo-0` in namespace `otel` on 2026-11-21 at the memory limit of `k8s/otel/tempo-values.yaml:39:memory: 2048Mi`, because the values set no limit on a search or on the size of a trace, so a search could hold the memory of the pod and the spans of the restart window were lost (#6616).

## What Changes

- Set `tempo.queryFrontend.search.max_bytes_per_trace` to `1000000`, `max_result_limit` to `50`, `max_duration` to `30s` and `target_bytes_per_second` to `25000000` in `k8s/otel/tempo-values.yaml`, which cut the bytes of a trace that a search reads, the number of results, the search time and the read rate.
- Set `tempo.queryFrontend.max_outstanding_per_tenant` to `10` and `tempo.querier.max_concurrent_queries` to `4` in the same file, under the unchanged limit at `k8s/otel/tempo-values.yaml:39:memory: 2048Mi`, so ten outstanding searches of fifty results of one million bytes hold 500000000 bytes, under the 1073741824 bytes of half of the limit, and at most four queries hold memory at once.
- Set `tempo.global_overrides.max_bytes_per_trace` to `1000000`, which cuts a trace above one million bytes when Tempo pushes it, so every trace that the store receives after the change is at most 1000000 bytes, and the retention of `k8s/otel/tempo-values.yaml:32:retention: 168h` removes the larger traces that the store held before it.
- Add `tests/gate/k8s_checks/tempo_query_limits.py`, whose `check_the_tempo_query_limits_stay_under_the_memory_limit` the `k8s` row runs, so a limit that lets the outstanding searches hold more than half of the memory limit, a querier that admits more queries than the outstanding-search limit, a missing trace size cut, or a changed memory limit fails the row.
- Carry the spec delta of `workload-resource-limits`, because a Helm values file is a manifest whose behavior a consumer observes.
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

- The probes confirm the premise of the issue, word for word: "The path `k8s/otel/tempo-values.yaml` is a file of the staging commit."
- read_file `k8s/otel/tempo-values.yaml` lines 20 to 45 showed the limit that the issue names, `k8s/otel/tempo-values.yaml:39:memory: 2048Mi`, the retention `k8s/otel/tempo-values.yaml:32:retention: 168h`, and no query limit: the `tempo:` block holds `securityContext`, `reportingEnabled`, `retention` and `resources` only.
- git_show f209f6c8 on `k8s/otel/tempo-values.yaml` showed the `config` override that the commit removed, whose `query_frontend:` block took `.Values.tempo.queryFrontend`, whose `querier:` block took `.Values.tempo.querier` and whose `overrides:` block took `{{- toYaml .Values.tempo.global_overrides | nindent 2 }}`; so the chart renders those three Tempo blocks from those three value keys, and the change sets keys that the chart maps.
- The review finding is fixed at its place. No line of the plan says that the per-tenant trace size cut bounds a read of a trace by id: `what_changes` says that `tempo.global_overrides.max_bytes_per_trace` cuts a trace when Tempo pushes it, and the read path of a trace by id is bounded by `tempo.querier.max_concurrent_queries` of `4` and by the retention of 168h that removes the traces the store held before the change, with the live reproduction as the proof that the pod stays up.
- search_code `queryFrontend` returned `No match.` on the staged tree: the chart is no file of the repository, so the plan sets the three value keys that the removed template renders and no other key.
- list_files `tests/gate/k8s_checks` showed 21 files, `__init__.py` and 20 check modules, and none of them names Tempo; read_file `tests/gate/k8s_checks/telemetry_resource.py` showed the shape of a check, with `tests/gate/k8s_checks/telemetry_resource.py:14:import yaml` and `tests/gate/k8s_checks/telemetry_resource.py:17:from tests.support.paths import REPO_ROOT`.
- read_file `tests/gate/runner.py` showed that a new module joins the row with no registration: `tests/gate/runner.py:32:def _check_modules(package: ModuleType) -> list[ModuleType]:` imports every module of the package, and `tests/gate/runner.py:45:if name.startswith("check_") and function.__module__ == module.__name__` selects each function named `check_`.
- read_file `tests/support/paths.py` showed the root that the check reads through, `tests/support/paths.py:21:REPO_ROOT: Final[Path] = TESTS_ROOT.parent`.
- The check calls `yaml.safe_load` and `Path.read_text` on `k8s/otel/tempo-values.yaml`; both need a checkout of the repository, and neither needs a client of a service nor a network.
- The verify program of both groups is `uv run devops ci --check --only k8s`: `uv`, `devops`, `python` and `kubectl` are image tools, and no program of the plan is `NOT_IN_RUNNER`; the row renders the tree with `kubectl kustomize` and needs no cluster. A failed row stops the step with the class `test`, whose action is `repair`.
- The check writes no file, so the pod settings `readOnlyRootFilesystem: true`, `capabilities.drop: ALL`, `runAsNonRoot: true` and `seccompProfile: RuntimeDefault` need no change.
- read_file `k8s/argocd/apps/tempo.yaml` showed chart `tempo` at `k8s/argocd/apps/tempo.yaml:13:targetRevision: 3.2.1`, with `k8s/argocd/apps/tempo.yaml:16:- $values/k8s/otel/tempo-values.yaml`, so the change moves no chart version.
- find_issues `tempo` listed 10 open items, this one included, and no title of the nine others names the Tempo values file or a query limit, so no open item overlaps this change.
- The probe bound left these names unprobed, word for word: "Not probed, the bound of 10 commands is reached: `querier.max_concurrent_queries`, `tempo.config`, `and.proposal`, `otel`, `OOMKilled`, `max_bytes_per_trace`, `Running`, `max_result_limit`, `max_duration`, `target_bytes_per_second`, `config`"
- This run ran no cluster command and sent no request to Tempo: it read no pod state, no ConfigMap and no trace. The two live checks below run against the real system and need a client of the cluster, and neither of them ran in this run.
- The first live check, which this run did not run, is `kubectl -n otel get configmap -l app.kubernetes.io/name=tempo -o yaml`, and its output must show `max_bytes_per_trace: 1000000` in the overrides along with `max_result_limit: 50`, `max_duration: 30s`, `target_bytes_per_second: 25000000`, `max_outstanding_per_tenant: 10` and `max_concurrent_queries: 4`.
- The second live check, which this run did not run, repeats the reproduction: `kubectl -n otel port-forward svc/tempo 13200:3200`, then ten requests `GET /api/search?q={name="invoke_agent agent"}&start=<t-900>&end=<t+120>&limit=50&spss=20` over the busy hour and one request for the trace of each id that a search returns, with the restart count of pod `tempo-0` read before and after them.
- The live check compares the restart count before and after the ten searches and the trace reads, and not with 0, because the issue records the two earlier restarts: "The restart count went to 2."
- The issue can be built as written: the file that it cites is at the staged commit, the memory limit is the 2048Mi that it names, and the chart renders the `query_frontend`, `querier` and `overrides` blocks from the values that the change sets.

## Existing Tool Considered

Grafana Tempo (grafana/tempo, AGPL-3.0, maintained, last activity 2026-11-21), which the project already runs as its trace backend and which ships the search byte, result, duration and byte-rate limits, the outstanding-search limit per tenant, the querier concurrency limit and the per-tenant trace size cut, that the change sets in the chart values. The change builds no replacement code and deletes no internal code, so it has no cost to build or keep.

## Dependencies

None.
