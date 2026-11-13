# Proposal: #5292

## Why

The homelab environment moves to its own private repository (tracker #5120, phase 2). Some files under `k8s/monitoring/` are product content and not environment content: the 3 dashboards that read the `devops_cli_*` series (`devops-cli.json`, `ai-spend.json`, `project-metrics.json`) and the 9 alert rule groups that watch them. They are in the same files as the environment content, so the copy of the environment cannot leave them behind (#5292). The environment Ingress routes also hold a copy of the Ingress `devops/roadmap-service`, which a delete patch of the ingress overlay removes again. This change is step 2 of the corrected plan on #5120: it splits the product content in place, and no file leaves the repository.

## What Changes

- The 3 product dashboards move to `k8s/devops/dashboards/`, with their own kustomization: namespace `monitoring`, the same generator options and the ConfigMap `grafana-devops-cli-dashboards`. `k8s/monitoring/dashboards/kustomization.yaml` lists `../../devops/dashboards`, so Application `monitoring` stays the owner of the ConfigMap. `k8s/devops/kustomization.yaml` does not list the folder, and a test fails when the overlay of Application `devops` reaches it.
- The 9 product rule groups (25 alerts) move to `k8s/devops/monitoring/prometheus-rules-values.yaml`, under the new key `serverFiles.devops_cli_alerting_rules.yml`. Application `prometheus` gives the chart this file as its second `$values` file. The environment values set `serverFiles.prometheus.yml.rule_files` to the 4 rule files of the chart and the new file.
- The `values` field of each release of `HELM_RELEASES_BY_STACK` is a list (the typed `StackRelease`), and `deploy-stack` gives `helm upgrade` one `--values` for each file. The release `prometheus` lists both files.
- `devops grafana dashboards lint` takes one or more paths, and with no path it lints both folders in one run. `devops grafana dashboards sync` with no `--dir` syncs both folders.
- The test reader `tests/support/k8s_tree.chart_values` merges the values files of a chart source in order, as Helm does, so the checks of the chart pods read the values that the chart gets.
- The copy of the Ingress `devops/roadmap-service` in `k8s/ingress/ingress-routes.yaml` and the delete patch of `k8s/overlays/homelab/ingress` go. `k8s/devops/roadmap-service/ingress.yaml` is the one file that holds the Ingress.
- `k8s/argo-workflows/workflowtemplate-version.yaml` stays where it is. #5135 moves it with its release pin.
- Each test, fixture and document that read the old paths reads the new ones.
- A manifest and the options of two commands change, so the change has spec deltas. It fits one pull request.

## Capabilities

### New Capabilities

- `product-monitoring-content`: where the product dashboards and alert rules live, and how Argo CD and deploy-stack apply them.

### Modified Capabilities

- `k8s-helm-deploy`: the helm command of a release names each of its values files.
- `grafana-dashboard-lint`: lint and sync read both dashboard folders by default.
- `roadmap-service-webhooks`: only `k8s/devops` holds the Ingress of the webhook route.
- `ai-spend-alerts`, `crawl4ai-alerts`, `roadmap-service-alerts`: the rule groups are in the product values file.
- `ai-spend-pricing`, `command-telemetry`, `github-api-metrics`, `llm-slot-wait`, `metric-instruments`, `roadmap-service-counters`: the dashboards are in `k8s/devops/dashboards/`.

## Impact

- Render: `kubectl kustomize` of `k8s/monitoring`, `k8s/overlays/homelab/ingress`, `k8s/overlays/homelab/devops`, `k8s/devops` and `k8s` gives the same bytes before and after. `k8s/ingress` alone loses the copy of the Ingress; no Application renders that folder, and the native `infra` stack no longer applies the copy.
- `helm template` of prometheus 29.47.2 changes only the ConfigMap `prometheus-server`: `alerting_rules.yml` loses the 9 groups, the new key `devops_cli_alerting_rules.yml` holds them, and `prometheus.yml` names the new file in `rule_files`. The set of 71 alert rules is the same. The pod template has no checksum of the ConfigMap, so no pod restarts.
- After the merge, Application `cluster` updates the `valueFiles` of Application `prometheus`, and Application `prometheus` updates the ConfigMap. The config reloader makes Prometheus load the files again. The 9 product groups are new groups to Prometheus, because a group is known by its file and name, so their `for` timers start again one time. Argo CD prunes nothing.
- #5131 PR 1 changes `DEFAULT_GRAFANA_DASHBOARDS_DIRS` and the environment paths next. The copy to the private repository (plan step 9) leaves `k8s/devops/` behind.

## Feasibility

- The premise was checked against origin/main `f9ca1b4de` on 2026-11-13. `k8s/monitoring/prometheus-values.yaml` holds 20 groups and 71 alerts. The 9 groups that select a `devops_cli_` series (`roadmap-service`, `roadmap-service-webhooks`, `roadmap-service-activity`, `roadmap-service-items`, `roadmap-service-tools`, `crawl4ai`, `research`, `ai-spend`, `rag-ingest`) hold 25 alerts, not the 27 that the issue gives; no environment group selects such a series. The count at the plan base `7a158c4c3` is the same.
- The chart `prometheus-29.47.2.tgz` (from the release of prometheus-community/helm-charts): `templates/cm.yaml` writes each key of `.Values.serverFiles` to the ConfigMap of the server, and `values.yaml` gives `serverFiles."prometheus.yml".rule_files` the 4 defaults under `/etc/config`. Helm replaces a list, so the environment values name the defaults again. `helm template` (Helm 4.3.1) with both files gives the same 12 objects, and the same 71 alert rules with the same content.
- promtool 3.15.1 `check rules` accepts both rendered rule files: 46 rules and 25 rules.
- Kustomize 5.8.1 (`kubectl kustomize`, kubectl 1.37.2) accepts a folder resource outside the kustomization root, and the renders of the touched Argo CD paths are byte for byte the same.
- The two copies of the Ingress `devops/roadmap-service` are the same object, and the ingress overlay deletes the copy of `k8s/ingress/ingress-routes.yaml`.
- `docs/generator.py:985-991` names `k8s/monitoring/prometheus-values.yaml` for the server flag `created-timestamp-zero-ingestion`, which stays in the environment values, so the generated text stays true.

## Existing Tool Considered

- Kustomize resources, the `serverFiles` values of the prometheus chart and the multi-source `$values` ref of Argo CD cover the split. The change adds no tool.
- The test reader merges two values files with a 10-line recursive function. No dependency of the project merges mappings as Helm does, and a test reads files only, so it cannot run `helm template`.
- Deleted: the copy of the Ingress `devops/roadmap-service` in `k8s/ingress/ingress-routes.yaml`, the delete patch of `k8s/overlays/homelab/ingress`, and the test that required the copy.
