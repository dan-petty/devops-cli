# Task: Resolve Argo CD Application Out-Of-Sync and Manifest Generation Failures (#1279)

**Issue**: [#1279](https://github.com/dan-petty/devops-cli/issues/1279)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
Argo CD applications were in degraded/out-of-sync or error states:
1. `ingress` application: Out of sync because `loki-ingress` had `port: null` in `k8s/overlays/homelab/ingress/kustomization.yaml` and blank port in `k8s/ingress/ingress-routes.yaml`, failing Kubernetes Ingress schema validation.
2. `base` and `monitoring` applications: Out of sync due to resource ownership conflicts:
   - Root `k8s/kustomization.yaml` included `monitoring/dashboards` while the dedicated `monitoring` application also deployed Grafana dashboards in namespace `monitoring`.
   - `k8s/monitoring/service-aliases.yaml` created `Service/pyroscope`, which conflicted with the `pyroscope` Helm chart managed by the `infra` stack.
   These ownership collisions caused continuous synchronization churn (`SharedResourceWarning`).
3. `devops` application: Argo CD reported `ComparisonError: ... k8s/devops/configmap.yaml: no such file or directory` because `k8s/devops/configmap.yaml` was gitignored in PR #1256 and missing from the git repository. Furthermore, personal homelab configuration (`service.repos`, `machine_account`, and `hooks.<domain>`) needed a clean parameter override mechanism that prevents git drift and avoids checking private settings into git.

## Key Changes
- **Ingress Route Port Definition** (`k8s/ingress/ingress-routes.yaml`, `k8s/overlays/homelab/ingress/kustomization.yaml`):
  - Added valid `port: { number: 3100 }` under `backend.service` for `loki-ingress`.
- **Deduplicate Resource Ownership** (`k8s/kustomization.yaml`, `k8s/monitoring/service-aliases.yaml`):
  - Removed `monitoring/dashboards` from root `k8s/kustomization.yaml`, giving exclusive ownership of Grafana dashboards in namespace `monitoring` to the `monitoring` application.
  - Removed redundant `Service/pyroscope` definition from `k8s/monitoring/service-aliases.yaml`, leaving Pyroscope service management to the Pyroscope Helm chart.
- **Git Cleanliness & Argo CD Source Parameter Overrides** (`src/devops_cli/k8s/argocd_source.py`, `src/devops_cli/commands/k8s/cluster_argocd_source.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `.gitignore`):
  - Removed `/k8s/devops/configmap.yaml` from `.gitignore` and committed generic base ConfigMap template in git with abstract defaults.
  - Added `devops k8s argocd-source` command and `devops_cli.k8s.argocd_source` module to generate gitignored `.argocd-source.yaml` parameter overrides for Argo CD with Kustomize patches for `devops-cli-config` and `roadmap-service` Ingress (`hooks.<domain>`).
  - Added `.argocd-source*.yaml` and `**/.argocd-source*.yaml` to `.gitignore`.
  - Removed `ignoreDifferences` on `devops-cli-config` from `k8s/argocd/apps/devops.yaml` since parameter overrides reconcile natively in Argo CD with zero sync drift.
  - Removed hardcoded domain patches from `k8s/overlays/homelab/devops/kustomization.yaml` and `k8s/overlays/homelab/ingress/kustomization.yaml` in favor of dynamic `.argocd-source.yaml` generation.
  - Updated `deploy_stack` in `stack_lifecycle.py` to generate `.argocd-source.yaml` parameter overrides during stack deployment.
- **Tests** (`tests/test_k8s_configmap.py`, `tests/test_k8s_argocd_source.py`, `tests/test_k8s_argocd_apps.py`, `tests/test_k8s_monitoring_dashboards.py`, `tests/test_k8s_monitoring_integration.py`):
  - Added unit tests for `render_argocd_source_content` and `generate_argocd_source` covering ConfigMap patches, Ingress patches, timeout options, and directory safety.
  - Added CLI tests for `devops k8s argocd-source` covering dry run, custom domain option, and missing template error handling.
  - Updated dashboard kustomization test to verify root kustomization leaves dashboards to the `monitoring` stack.
  - Updated monitoring integration test to account for Helm-managed services when checking addressed monitoring services.

## Acceptance Criteria
- [x] Ingress application syncs cleanly without schema validation errors on `loki-ingress`.
- [x] Base and monitoring applications no longer suffer ownership conflicts over Grafana dashboards or Pyroscope service.
- [x] Devops application manifests build successfully with kustomize in Argo CD.
- [x] `kubectl kustomize k8s/overlays/homelab/devops` and `k8s/overlays/homelab/ingress` generate valid manifests with exit code 0.
- [x] `devops k8s argocd-source` renders and generates gitignored `.argocd-source.yaml` files without dirtying git.
- [x] All unit and integration tests pass.
- [x] `uv run devops ci` completes with 100% passing status.
