# Tasks

## 1. Add the two SM profiling fields to the exporter counter list

Kind: other. Reads: `k8s/monitoring/dcgm-exporter-values.yaml`, `k8s/argocd/apps/dcgm-exporter.yaml`, `tests/ai/test_llm_pool_metrics.py`. Changes: `k8s/monitoring/dcgm-exporter-values.yaml`, `tests/ai/test_llm_pool_metrics.py`.

- [x] 1.1 Add `DCGM_FI_PROF_SM_ACTIVE` and `DCGM_FI_PROF_SM_OCCUPANCY` to the `# Profiling (DCP) fields` block of `customMetrics` in `k8s/monitoring/dcgm-exporter-values.yaml`, each as a `gauge` line whose help text says that the value is a ratio from 0 to 1. Change the comment above the list, which counts the fields added to the image's list, to four. Replace the value of `podAnnotations.checksum/counters` with the SHA-256 of the new `customMetrics` text, and leave every other line of the file as it is, and run this check by hand: 1. Run `git diff -- k8s/monitoring/dcgm-exporter-values.yaml` and confirm that the diff adds the two gauge lines, changes the comment and the `checksum/counters` value, and touches nothing else. 2. Before the edit, run a short `uv run python` script that reads the `customMetrics` block of `k8s/monitoring/dcgm-exporter-values.yaml` and prints the SHA-256 of its text, and confirm that it prints the staged value `f636a5dfff8c116f098785682de1789ee698a46ab69bbde4c79fed13963665a6`, so the script hashes the same text that the annotation holds. 3. After the edit, run the same script and set `checksum/counters` to its answer. 4. Confirm that `arguments` is absent, that the `securityContext` block is unchanged, and that the two new lines are the only fields added

## 2. Add the GPU SM activity and occupancy panel to the GPU row

Kind: manifest. Reads: `k8s/monitoring/dashboards/llm-stack.json`, `tests/prometheus/test_dashboard_queries.py`, `tests/fixtures/dashboard_queries/project-metrics.yaml`, `docs/TESTING.md`. Changes: `k8s/monitoring/dashboards/llm-stack.json`, `tests/fixtures/dashboard_queries/llm-stack.yaml` (new).

- [x] 2.1 the two cases of the panel `GPU SM Activity and Occupancy` in `tests/fixtures/dashboard_queries/llm-stack.yaml`, which make `tests/prometheus/test_dashboard_queries.py` fail with `0 targets, not 1` before the panel exists
  - Verification: `$ uv run devops ci test tests/prometheus/test_dashboard_queries.py` fails on the base
- [x] 2.2 Add the panel `GPU SM Activity and Occupancy` to the GPU row of `k8s/monitoring/dashboards/llm-stack.json` with id 39, type `timeseries`, gridPos x 0, y 83, w 24, h 8, unit `percentunit`, min 0, max 1, the legend format `{{hostname}} GPU {{gpu}} ({{modelName}})`, and a description that names the Quadro P6000 and the GeForce RTX 3090 as the cards that report no profiling field. Give it two targets, `avg by (hostname, gpu, modelName) (DCGM_FI_PROF_SM_ACTIVE)` at refId A and `avg by (hostname, gpu, modelName) (DCGM_FI_PROF_SM_OCCUPANCY)` at refId B. Move the row `Qdrant` from y 83 to y 91 and every panel after it down by 8. Add `tests/fixtures/dashboard_queries/llm-stack.yaml` in the format of `tests/fixtures/dashboard_queries/project-metrics.yaml`, with one test group of `shape: snapshot_gauge`, input series for the Tesla PG500-216 and the GeForce RTX 5070 Ti cards, and one `promql_expr_test` case for each target, whose `expr` is the panel query exactly and whose `exp_samples` `promtool test rules` confirms
  - Verification: `$ uv run devops ci test tests/prometheus/test_dashboard_queries.py` passes

## Criteria

- Pending person: The deployed exporter on each card that supports profiling serves both fields, and its log has no `Failed to watch DCGM fields`., Only a person with a client of the cluster can read `/metrics` through `kubectl port-forward` and the pod log after Argo CD rolls the DaemonSet; the runner has no cluster token and `kubectl` is NOT_IN_RUNNER.
- Pending person: The panel shows a series for at least one GPU., Only a person can open the panel on Grafana after the rollout; the runner reaches no Grafana and no Prometheus, and the panel draws no line until the deployed exporter serves the two fields.
- Group 2: `uv run devops ci test tests/test_stack_dashboards.py` passes.
