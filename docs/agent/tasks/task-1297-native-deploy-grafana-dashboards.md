# Task: A Native deploy-stack Applies the Grafana Dashboards Again (#1297)

**Issue**: [#1297](https://github.com/dan-petty/devops-cli/issues/1297)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
Copilot thread 5 on release PR #1283, verified at 61f9b67. #1279 (3f02ee9) removed `monitoring/dashboards` from the root `k8s/kustomization.yaml`, so that Argo CD's `monitoring` Application alone owns the dashboard ConfigMaps. A native `devops k8s deploy-stack --stack infra` applies only that root kustomization and `_MANIFESTS_BY_STACK["infra"]`, so it no longer created any Grafana dashboard. `k8s/README.md` and the dashboards kustomization's comment still said the root kustomization applies them.

The dashboards stay out of the root kustomization. The native path applies the dashboards kustomization on its own with `kubectl apply -k`; it cannot be a manifest in `_MANIFESTS_BY_STACK`, because those go through `kubectl apply -f`, which would read the dashboard JSON files and `kustomization.yaml` as objects. Applying all of `k8s/monitoring` instead would also apply `monitoring/networkpolicy.yaml`, which the native path never applied.

## Key Changes
- **deploy-stack** (`src/devops_cli/commands/k8s/stack_lifecycle.py`):
  - `_KUSTOMIZATIONS_BY_STACK` maps the `infra` stack to `monitoring/dashboards`, relative to `--k8s-dir`, with a comment on why the root leaves it out (#1279).
  - `deploy_stack` collects the selected stacks' kustomizations alongside their manifests. On a cluster Argo CD does not manage, `_apply_kustomizations` runs `kubectl apply -k` on the root and then on each of them, so the `monitoring` namespace exists first.
  - The dry run lists them under `kustomizations`.
  - The Argo CD-managed path returns before any apply and is unchanged. Teardown needs no change: `--stack infra` deletes the `monitoring` namespace, and `all` deletes the namespaces through the root.
- **Docs**:
  - `k8s/README.md` "Grafana Dashboards" says Argo CD's `monitoring` Application applies the dashboards on a cluster it manages, and `deploy-stack --stack infra` (or `all`) applies `monitoring/dashboards` without Argo CD. The directory tree no longer lists Grafana dashboard ConfigMaps under the root kustomization, and names the monitoring Service aliases it does apply.
  - `k8s/monitoring/dashboards/kustomization.yaml` names both paths in its "Applied by" comment.

## Acceptance Criteria
- [x] A native `deploy-stack --stack infra` applies `k8s/monitoring/dashboards` after the root kustomization (`test_native_deploy_stack_infra_applies_the_grafana_dashboards` in `tests/test_k8s.py`, which fails at 61f9b67).
- [x] The dry run of `infra` and `all` lists `k8s/monitoring/dashboards` under `kustomizations`, and that of `llm` lists none (`test_deploy_stack_dry_run_lists_the_kustomizations_its_stacks_apply` in `tests/test_k8s.py`).
- [x] The Argo CD path is unchanged, and the root kustomization still leaves the dashboards to the `monitoring` Application (`test_root_kustomization_leaves_dashboards_to_monitoring_stack` in `tests/test_k8s_monitoring_dashboards.py`).
- [x] `k8s/README.md` and the dashboards kustomization's comment say which path applies the dashboards.
- [x] `changelog.d/1297.md` records the change; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.
- Pending a person: on a cluster Argo CD does not manage, run `uv run devops k8s deploy-stack --stack infra`, then `kubectl -n monitoring get configmap -l grafana_dashboard=1` lists the four dashboard ConfigMaps and Grafana shows their dashboards.
