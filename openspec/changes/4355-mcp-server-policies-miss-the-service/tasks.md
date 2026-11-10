# Tasks

## 1. The policies admit the Job pods

- [x] 1.1 Write the failing test: the label that the two policies admit equals the pod label of `build_job`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_mcp_server_policies.py`
- [x] 1.2 Select `devops-cli-job` in both policies
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_mcp_server_policies.py tests/invariants/test_k8s_manifests.py`

## 2. Documents

- [x] 2.1 Update `k8s/README.md` and `SECURITY.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person, after the merge and the Argo CD sync: the check of the policies and the live ConfigMap step (steps in the pull request comment).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
