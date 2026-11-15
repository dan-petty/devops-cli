# Tasks

## 1. Add invariant tests for GPU feature discovery security context

Kind: test. Reads: `k8s/gpu-feature-discovery/daemonset.yaml`. Changes: `tests/invariants/test_k8s_gpu_feature_discovery.py`.

- [x] 1.1 Add `test_the_gpu_feature_discovery_container_sets_a_read_only_root_filesystem` and `test_the_gpu_feature_discovery_container_keeps_privileged_gpu_access` to `tests/invariants/test_k8s_gpu_feature_discovery.py` to assert `readOnlyRootFilesystem: true`, `privileged: true`, and volume mounts
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_gpu_feature_discovery.py` fails on missing field

## 2. Configure read-only root filesystem in DaemonSet

Kind: config. Reads: `k8s/gpu-feature-discovery/daemonset.yaml`. Changes: `k8s/gpu-feature-discovery/daemonset.yaml`.

- [x] 2.1 Set `readOnlyRootFilesystem: true` under container `securityContext` in `k8s/gpu-feature-discovery/daemonset.yaml`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_gpu_feature_discovery.py` passes
