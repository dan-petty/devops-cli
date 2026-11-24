# Tasks

## 1. Workload Removal

- [x] 1.1 Remove k8s/devops/renovate manifests and kustomization entry
  - Verification: `$ git ls-files k8s/devops/renovate | wc -l`
- [x] 1.2 Remove renovate manifest paths from stack_lifecycle.py
  - Verification: `$ git diff src/devops_cli/commands/k8s/stack_lifecycle.py`
- [x] 1.3 Delete renovate_token.py, gate check, invariant test, and support files
  - Verification: `$ git ls-files src/devops_cli/k8s/renovate_token.py tests/invariants/test_k8s_renovate.py tests/gate/k8s_checks/renovate.py | wc -l`
- [x] 1.4 Move secret row test to tests/k8s/test_cluster_secrets.py
  - Verification: `$ uv run pytest tests/k8s/test_cluster_secrets.py`
- [x] 1.5 Update devops_runtime.py and telemetry_resource.py
  - Verification: `$ uv run pytest tests/gate/k8s_checks/`

## 2. Documentation and Verification

- [x] 2.1 Update docs/CLUSTER.md, docs/TESTING.md, and .trivyignore.yaml
  - Verification: `$ git diff docs/ .trivyignore.yaml`
- [x] 2.2 Run scoped CI checks
  - Verification: `$ uv run devops ci --check --only test,k8s,kube-linter,docs,openspec`
