# Proposal

## Why

The GPU row of the LLM stack dashboard has no SM activity or SM occupancy panel, and the deployed exporter does not ask the DCGM profiling module for the two fields, so a person cannot tell how busy the streaming multiprocessors of a card are. #2407 adds the two fields to the counter list that the deployed exporter reads and draws them in the GPU row, because the profiling module serves one client per GPU and the deployed exporter pod is that client.

## What Changes

- Add `DCGM_FI_PROF_SM_ACTIVE` and `DCGM_FI_PROF_SM_OCCUPANCY` as gauge lines to the profiling block of `customMetrics` in `k8s/monitoring/dcgm-exporter-values.yaml`, and change the comment above the list to count four fields added to the image's list.
- Set `podAnnotations.checksum/counters` to the SHA-256 of the new `customMetrics` text, so the DaemonSet rolls onto the list that the exporter reads.
- Add the panel `GPU SM Activity and Occupancy` to the GPU row of `k8s/monitoring/dashboards/llm-stack.json`, with id 39, unit `percentunit`, min 0 and max 1, one target for each field aggregated `avg by (hostname, gpu, modelName)`, and a description that names the Quadro P6000 and the GeForce RTX 3090 as the cards that report no profiling field.
- Move the row `Qdrant` from y 83 to y 91 and every panel after it down by 8 grid units, so the new panel fills y 83 and the dashboard lint reports no overlap.
- Add `tests/fixtures/dashboard_queries/llm-stack.yaml` with one promtool case for each of the two targets, so the dashboard-query test fails before the panel exists and passes after it.
- The change carries a spec delta: it adds a requirement to `llm-stack-dashboard` and modifies the counter-list requirement of `dcgm-exporter`, because a dashboard and a Helm values file are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `llm-stack-dashboard`: The GPU row shows SM activity and SM occupancy
- `dcgm-exporter`: The DCGM exporter collects the counter list of its values and restarts when the list changes

## Impact

- Code: `k8s/monitoring/dcgm-exporter-values.yaml`, `k8s/monitoring/dashboards/llm-stack.json`
- Tests: `tests/ai/test_llm_pool_metrics.py`, `tests/fixtures/dashboard_queries/llm-stack.yaml`

## Feasibility

- The probe lines of this run name the two cited paths, word for word: The path `k8s/monitoring/dashboards/llm-stack.json` is a file of the staging commit. And: The path `k8s/monitoring/dcgm-exporter-values.yaml` is a file of the staging commit.
- `read_file` of `k8s/monitoring/dcgm-exporter-values.yaml` confirmed the premise: the counter list starts at `k8s/monitoring/dcgm-exporter-values.yaml:50:customMetrics: |`, the profiling block starts at `k8s/monitoring/dcgm-exporter-values.yaml:101:# Profiling (DCP) fields`, and its last line is `k8s/monitoring/dcgm-exporter-values.yaml:106:DCGM_FI_PROF_PCIE_RX_BYTES`, so the deployed list asks for neither SM field.
- The same file gives the two staged constants that the plan relies on: `image.tag` is `4.6.1-4.8.4-distroless` at `k8s/monitoring/dcgm-exporter-values.yaml:12:tag: 4.6.1-4.8.4-distroless`, and `podAnnotations.checksum/counters` is `f636a5dfff8c116f098785682de1789ee698a46ab69bbde4c79fed13963665a6` at `k8s/monitoring/dcgm-exporter-values.yaml:41:checksum/counters: "f636a5dfff8c116f098785682de1789ee698a46ab69bbde4c79fed13963665a6"`.
- `read_file` of the same file showed the comment that counts the added fields at `k8s/monitoring/dcgm-exporter-values.yaml:45:# the image's dcp-metrics-included.csv (4.8.4) with two more fields: the enforced power limit and`, so the plan changes its count to four.
- `read_file` of `k8s/monitoring/dashboards/llm-stack.json` showed that the last panel of the GPU row ends at `k8s/monitoring/dashboards/llm-stack.json:1379:"y": 75` with height 8, that the next row is at `k8s/monitoring/dashboards/llm-stack.json:1417:"title": "Qdrant"` with `k8s/monitoring/dashboards/llm-stack.json:1423:"y": 83`, and that no panel holds id 39, so the new panel takes y 83 and the Qdrant row and the panels after it move down by 8.
- The panel copies the label set of the row's profiling panel at `k8s/monitoring/dashboards/llm-stack.json:1399:"expr": "max by (hostname, gpu, modelName) (DCGM_FI_PROF_PCIE_RX_BYTES)"` and the sentence that names the cards without profiling support at `k8s/monitoring/dashboards/llm-stack.json:1360:The Quadro P6000 and the GeForce RTX 3090 have no line.`
- `read_file` of `tests/prometheus/test_dashboard_queries.py` showed the case-file discovery at `tests/prometheus/test_dashboard_queries.py:53:CASE_FILES = sorted((FIXTURES / "dashboard_queries").glob("*.yaml"))`, the comparison in `tests/prometheus/test_dashboard_queries.py:def query_mismatches`, and the shape census in `tests/prometheus/test_dashboard_queries.py:def test_the_cases_hold_each_series_shape`; `list_files` of `tests/fixtures/dashboard_queries` listed seven case files and no `llm-stack.yaml`, so the case file is new.
- `search_code` for `checksum/counters` returned only `k8s/monitoring/dcgm-exporter-values.yaml:41:checksum/counters: "f636a5dfff8c116f098785682de1789ee698a46ab69bbde4c79fed13963665a6"` and archived change text, so no test of the staging commit asserts the digest.
- `search_code` for `dashboards lint` returned `docs/commands/grafana.md:152:devops grafana dashboards lint [OPTIONS] <paths>`, so the lint command of the added scenario exists.
- `file_symbols` of `tests/ai/test_llm_pool_metrics.py` listed `tests/ai/test_llm_pool_metrics.py:def test_the_dcgm_exporter_runs_on_every_gpu_node_without_extra_privileges`, which reads the values file for the runtime class, the node selector, the tolerations, the capabilities, the rolling update and the ServiceMonitor, so two more counter lines change no test; the plan reads that file and changes it in no group.
- The probe lines name two cited paths that the staging commit does not hold, word for word: The path `tests/fixtures/metrics/dcgm-exporter.yaml` is no file at the root of the staging commit. These files of the commit are candidates: `k8s/argocd/apps/dcgm-exporter.yaml`. Commit d4968f6b 2026-11-16 fix(k8s): Drop the tests that assert values of manifests and config (#6075) deleted or renamed it. And: The path `tests/test_stack_dashboards.py` is no file of the staging commit. Commit 513bb31f 2026-10-30 test(cli): tests mirror package directories and trim root conftest (#2830) deleted or renamed it.
- The probe line says `dcp-metrics-included.csv` is no file of the staging commit, so the plan reads no such file and names the counter list only at `k8s/monitoring/dcgm-exporter-values.yaml`.
- The plan compensates for neither deleted path: it adds no metrics fixture and creates no stack-dashboard test module, because `docs/TESTING.md:62:The `test-tree` row of `devops ci` refuses a new test that reads a committed manifest or config file` and `tests/gate/tree_checks/config_reads.toml:6:No line is added.` hold the module counts, and `tests/gate/tree_checks/config_reads.toml:66:"tests/prometheus/test_dashboard_queries.py" = 7` fixes the count of the only module that reads a dashboard.
- The `criterion_dropped` finding is answered at its place: the third criterion names `tests/test_stack_dashboards.py`, which commit 513bb31f deleted, so no command can run it; the plan maps the criterion to group 2, whose `verify` runs `uv run devops ci test tests/prometheus/test_dashboard_queries.py`, the dashboard check that replaced the deleted module, and the group changes the panel and the case that this check reads, so a task delivers the criterion and no person has to amend the issue.
- The plan calls no function of the repository whose arguments need a checkout, a client or a network; the only calls that need one are the live check commands, whose preconditions are a client of the cluster and a network to its API server.
- The verify program `uv run devops ci test tests/prometheus/test_dashboard_queries.py` runs `pytest` and `promtool`, both in the runner image, under the pod settings `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`; a failing case is failure class `test` with action `repair`, and a missing `promtool` is `ci_infra` with action `retry`.
- The manual check of group 1 runs `git diff` and `uv run python`, both in the runner image; the live check of the deployed exporter runs `kubectl` and `helm`, which are `NOT_IN_RUNNER`, on a workstation with a client of the cluster.
- The first checks against the real system after the merge, each with its command: `kubectl -n monitoring port-forward daemonset/dcgm-exporter 9400:9400` then `curl -s http://localhost:9400/metrics | grep -E 'DCGM_FI_PROF_SM_(ACTIVE|OCCUPANCY)'` on the Tesla PG500-216 and GeForce RTX 5070 Ti nodes, `kubectl -n monitoring logs daemonset/dcgm-exporter | grep "Failed to watch DCGM fields"` which must print nothing, and `uv run devops ci --check --only k8s` for the rendered dashboard.
- The check of the previous reply is corrected at its two places: the modified `dcgm-exporter` requirement text is now 445 characters and moves the mount path and the type detail into its scenarios, and the What Changes item for the promtool case names the dashboard-query test as plain words with no repository path, so no path of `what_changes` sits outside a group's `changes` or `creates`.

## Existing Tool Considered

NVIDIA/dcgm-exporter (https://github.com/NVIDIA/dcgm-exporter), Apache-2.0, maintained: release 4.8.4 is the deployed DaemonSet and serves `DCGM_FI_PROF_SM_ACTIVE` and `DCGM_FI_PROF_SM_OCCUPANCY` as gauges once its counter list asks for them, so the change adds two lines to that list and one panel to the existing dashboard, and builds no code.

## Dependencies

None.
