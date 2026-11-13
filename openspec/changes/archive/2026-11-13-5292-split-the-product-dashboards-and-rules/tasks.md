# Tasks

## 1. The product dashboards

Kind: behavior.

- [x] 1.1 Write the failing tests: `k8s/devops/dashboards` generates `grafana-devops-cli-dashboards` in `monitoring` and the dashboards kustomization of `k8s/monitoring` lists it; the overlay of Application `devops` does not reach it; `grafana dashboards lint` with no path and `sync` with no `--dir` read both folders.
  - Verification: `$ uv run pytest tests/prometheus/test_k8s_monitoring_dashboards.py tests/grafana/test_grafana_dashboards.py tests/commands/test_grafana.py -q`
- [x] 1.2 Move the 3 dashboards with their kustomization, list the folder in `k8s/monitoring/dashboards/kustomization.yaml`, replace `DEFAULT_GRAFANA_DASHBOARDS_DIR` with `DEFAULT_GRAFANA_DASHBOARDS_DIRS`, let `lint` take several paths, and re-point each test and fixture that reads the dashboards.
  - Verification: `$ uv run pytest tests/prometheus tests/grafana tests/commands/test_grafana.py tests/commands/k8s/test_stack_dashboards.py tests/telemetry/test_telemetry_instruments.py -q`

## 2. The product alert rules

Kind: behavior.

- [x] 2.1 Write the failing tests: the environment values name the 4 rule files of the chart and the product file in `rule_files`; the product file holds the 9 groups that select a `devops_cli_` series; a group name is unique; promtool accepts each file; the helm command of release `prometheus` names both values files.
  - Verification: `$ uv run pytest tests/prometheus/test_k8s_monitoring_alerting.py tests/commands/k8s/test_k8s.py -q`
- [x] 2.2 Move the 9 groups to `k8s/devops/monitoring/prometheus-rules-values.yaml`, set `rule_files`, add the file to Application `prometheus`, make the `values` field of `HELM_RELEASES_BY_STACK` a list, and merge the values files of a chart source in `tests/support/k8s_tree.py`.
  - Verification: `$ uv run pytest tests/prometheus tests/commands/k8s tests/invariants tests/core/test_k8s_local_path_placement.py tests/ai/test_llm_pool_metrics.py tests/ai/benchmark/test_k8s_llm_gateway.py -q`

## 3. The Ingress of the webhook route

Kind: manifest.

- [x] 3.1 Delete the copy of the Ingress `devops/roadmap-service` in `k8s/ingress/ingress-routes.yaml` and the delete patch of `k8s/overlays/homelab/ingress`, and change the test and the gate check that read the copy.
  - Verification: `$ uv run devops ci --check --only k8s`

## 4. Documents

Kind: other.

- [x] 4.1 Update the dashboards, alerting, roadmap Service, Crawl4AI and tree sections of `k8s/README.md`, `docs/TESTING.md`, `docs/DASHBOARD_TABS_AUDIT.md` and the Purpose of two dashboard specs, and regenerate the command pages.
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- #5131 makes the dashboard folders and the other environment paths settings of the infra repository.
- #5135 moves `k8s/argo-workflows/workflowtemplate-version.yaml` with its release pin.
- #5293 moves the product sections of `k8s/README.md` to `docs/`.
- Pending a person: after the merge, `argocd app diff --core --exit-code` is 0 for each Application except `cluster` and `prometheus`, Argo CD prunes nothing, and the rule API of Prometheus shows 71 alert rules.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
