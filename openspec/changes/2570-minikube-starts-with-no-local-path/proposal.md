# Proposal

## Why

#2570: the devcontainer's minikube starts with no local-path StorageClass, so every PVC that names it stays Pending and the services that mount them cannot start.

## What Changes

- Add --addons=storage-provisioner-rancher to the minikube start command in _start_minikube
- Update k8s/README.md to state that devops devcontainer enables the addon automatically
- Add a unit test that asserts the start command includes the addon flag
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-bootstrap`: minikube start enables local-path storage

## Impact

- Code: `src/devops_cli/commands/k8s/cluster_runtime.py`
- Tests: `tests/test_k8s_cluster_runtime.py`

## Feasibility

- The issue premise is confirmed by the start command in src/devops_cli/commands/k8s/cluster_runtime.py (_start_minikube), which passes --driver=docker --cni=calico but no --addons flag.
- The k8s/README.md Prerequisites section states that devops devcontainer does not enable the storage-provisioner-rancher addon.
- Seven PVC files in the repository name local-path: k8s/devops/roadmap-service/pvc.yaml, k8s/gitea/values.yaml, k8s/monitoring/grafana-values.yaml, k8s/monitoring/k8s-monitoring-values.yaml, k8s/monitoring/prometheus-values.yaml, k8s/monitoring/pyroscope-values.yaml, k8s/otel/tempo-values.yaml.
- First check the implementation runs: uv run devops ci test tests/test_k8s_cluster_runtime.py to verify the start command includes the addon flag.
- Second check: uv run devops ci test to run the full test suite and confirm no regression.

## Existing Tool Considered

minikube's storage-provisioner-rancher addon provides the local-path StorageClass with the rancher local-path provisioner. It is listed in minikube v1.39.0 addons list. No new code is built.
