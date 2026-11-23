# Tasks

## 1. Quality Gates and Tests

- [x] 1.1 Add k8s gate checks for storage class and Argo CD ignore differences
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 Add invariant test for k8s storage documentation
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_storage_docs.py`
- [x] 1.3 Verify fail-to-pass on base
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`

## 2. Manifest Updates

- [x] 2.1 Update PersistentVolumeClaims and Helm values to local-path-retain
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 2.2 Add ignoreDifferences and RespectIgnoreDifferences to the seven Argo CD applications
  - Verification: `$ uv run devops ci --check --only k8s`

## 3. Documentation

- [x] 3.1 Update k8s/README.md and docs/SERVICE_PATTERNS.md
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_storage_docs.py`
