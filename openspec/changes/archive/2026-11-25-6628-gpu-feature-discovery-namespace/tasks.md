# Tasks

## 1. Behavior

- [x] 1.1 Write failing manifest and default-namespace tests in `tests/k8s/test_k8s_gpu_feature_discovery.py` and `tests/config/test_project_review_namespaces_setting.py`
  - Verification: `$ uv run pytest tests/k8s/test_k8s_gpu_feature_discovery.py tests/config/test_project_review_namespaces_setting.py`
- [x] 1.2 Move `gpu-feature-discovery` into its dedicated namespace across `k8s/namespaces.yaml`, `k8s/gpu-feature-discovery/daemonset.yaml`, `k8s/argocd/apps/gpu-feature-discovery.yaml`, `k8s/argocd/apps/projects.yaml`, and `src/devops_cli/config/defaults.py`
  - Verification: `$ uv run pytest tests/k8s/test_k8s_gpu_feature_discovery.py tests/config/test_project_review_namespaces_setting.py tests/k8s/ && uv run devops ci --check --no-cache --only k8s`

## 2. Documents

- [x] 2.1 Update `openspec/specs/homelab-project-destinations/spec.md` via OpenSpec archive and pass CI checks
  - Verification: `$ uv run devops ci --check --no-cache --only lint,format,typecheck,test-tree,docs,k8s,openspec`
