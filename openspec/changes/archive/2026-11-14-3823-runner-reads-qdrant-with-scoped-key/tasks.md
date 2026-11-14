# Tasks

## 1. The policies admit the Qdrant search path

- [x] 1.1 Add one egress rule to namespace `llm` on TCP 6333 in `k8s/devops/networkpolicy.yaml`.
  Verification: `uv run devops ci test tests/commands/k8s/test_k8s_network_policies.py tests/config/test_k8s_devops_runtime.py`
- [x] 1.2 Add one ingress rule from namespace `devops` on TCP 6333 in `k8s/llm/networkpolicy.yaml`.
  Verification: `uv run devops ci test tests/commands/k8s/test_k8s_network_policies.py`

## 2. The read-only key feeds Qdrant and the pods

- [x] 2.1 Read `QDRANT__SERVICE__READ_ONLY_API_KEY` from key `read-only-api-key` in `k8s/llm/values-qdrant.yaml`.
  Verification: `uv run devops ci test tests/commands/k8s/test_k8s_qdrant_security.py`
- [x] 2.2 Add the read-only row to Secret `llm/qdrant-api-key` and `DEVOPS_CLI_QDRANT_API_KEY` to Secret `devops/devops-cli`, both from keyring `qdrant_read_only_api_key`.
  Verification: `uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py`
- [x] 2.3 Name `qdrant.url` in `k8s/devops/configmap.example.yaml` and hold no key there.
  Verification: `uv run devops ci test tests/config/test_k8s_devops_runtime.py`

## 3. The documents name the route and the person step

- [x] 3.1 Add the route and the two Cluster Secrets rows to `k8s/README.md`, and name the read-only key in rule 1 of `SECURITY.md`.
  Verification: `uv run devops ci test tests/invariants/test_k8s_manifests.py tests/commands/k8s/test_k8s_network_policies.py`
- [x] 3.2 Run the quality gate and the k8s test tree.
  Verification: `uv run devops ci --check --only lint,format,typecheck && uv run devops ci test tests/k8s tests/commands/k8s tests/config tests/invariants`
