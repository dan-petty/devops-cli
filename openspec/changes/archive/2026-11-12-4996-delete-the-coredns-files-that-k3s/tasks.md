# Tasks

## 1. Tests and manifests

- [x] 1.1 Remove the CoreDNS entry from `_TOKEN_EXCEPTIONS` and the 384Mi assertions of `test_k8s_workload_resource_limits_and_probes`, and see `test_every_manifest_pod_with_a_token_has_a_role_or_a_named_exception` fail while the files exist
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_manifests.py tests/commands/k8s/test_k8s.py`
- [x] 1.2 Delete `k8s/coredns/helmchartconfig.yaml`, `k8s/coredns/deployment-patch.yaml` and `k8s/coredns/values.yaml`
  - Verification: `$ ! git grep -n -F k8s/coredns -- k8s src tests`

## 2. Documents

- [x] 2.1 State in `k8s/README.md` that k3s, not git, holds CoreDNS, with its live replicas, requests and limit, and remove the note and the exception item that named `k8s/coredns/`
  - Verification: `$ uv run devops ci docs`
