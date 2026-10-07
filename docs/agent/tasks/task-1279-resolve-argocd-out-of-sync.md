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
3. `devops` application: Argo CD reported `ComparisonError: ... k8s/devops/configmap.yaml: no such file or directory` because `k8s/devops/configmap.yaml` was gitignored in PR #1256 and missing from the git repository.

## Key Changes
- **Ingress Route Port Definition** (`k8s/ingress/ingress-routes.yaml`, `k8s/overlays/homelab/ingress/kustomization.yaml`):
  - Added valid `port: { number: 3100 }` under `backend.service` for `loki-ingress`.
- **Deduplicate Resource Ownership** (`k8s/kustomization.yaml`, `k8s/monitoring/service-aliases.yaml`):
  - Removed `monitoring/dashboards` from root `k8s/kustomization.yaml`, giving exclusive ownership of Grafana dashboards in namespace `monitoring` to the `monitoring` application.
  - Removed redundant `Service/pyroscope` definition from `k8s/monitoring/service-aliases.yaml`, leaving Pyroscope service management to the Pyroscope Helm chart.
- **Devops ConfigMap Git Tracking & Argo CD Ignore Differences** (`.gitignore`, `k8s/devops/configmap.yaml`, `k8s/argocd/apps/devops.yaml`):
  - Removed `/k8s/devops/configmap.yaml` from `.gitignore` and committed generic base ConfigMap template in git.
  - Added `ignoreDifferences` for `devops-cli-config` on `/data` in `k8s/argocd/apps/devops.yaml`, allowing runtime service configuration (`service.repos`, `machine_account`) to be pushed directly from local `config.yaml` via CLI without checking personal configuration into git.
- **Tests** (`tests/test_k8s_monitoring_dashboards.py`, `tests/test_k8s_monitoring_integration.py`):
  - Updated dashboard kustomization test to verify root kustomization leaves dashboards to the `monitoring` stack.
  - Updated monitoring integration test to account for Helm-managed services when checking addressed monitoring services.
- **Changelog Fragment** (`changelog.d/1279.md`):
  - Added fragment documenting fixes for issue #1279.

## Acceptance Criteria
- [x] Ingress application syncs cleanly without schema validation errors on `loki-ingress`.
- [x] Base and monitoring applications no longer suffer ownership conflicts over Grafana dashboards or Pyroscope service.
- [x] Devops application manifests build successfully with kustomize in Argo CD.
- [x] `kubectl kustomize k8s/overlays/homelab/devops` and `k8s/overlays/homelab/ingress` generate valid manifests with exit code 0.
- [x] All unit and integration tests pass.
- [x] `uv run devops ci` completes with 100% passing status.
