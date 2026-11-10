# Tasks

## 1. The token reaches the cluster

- [x] 1.1 Write the failing tests: the secret table rows, the push of the three keys, the `secretKeyRef` of Deployment `mcp-server`, and the guard over the keys that manifests read
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py tests/config/test_k8s_devops_runtime.py tests/invariants/test_k8s_manifests.py`
- [x] 1.2 Add the rows to `cluster_secrets.py`, the `secretKeyRef` to the Deployment, and `roadmap.mcp.url` to the ConfigMap example
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py tests/config/test_k8s_devops_runtime.py tests/invariants/test_k8s_manifests.py`

## 2. Documents

- [x] 2.1 Update `k8s/README.md`, `SECURITY.md` and the description of `mcp.token`, and regenerate `docs/ENV_VARS.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The NetworkPolicies of the MCP server miss the runner Jobs of the Service. The follow-up is #4355.
- Pending a person: run `devops k8s push-secrets --only devops/mcp-server --only devops/devops-cli`, then check that the pod is ready (steps in the pull request comment).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
