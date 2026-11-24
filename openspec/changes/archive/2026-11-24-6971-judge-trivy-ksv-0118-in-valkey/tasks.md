# Tasks

## 1. Fixture Fix and Test Update

Kind: other.

- [x] 1.1 Add restrictive pod and container `securityContext` blocks to `tests/fixtures/research/repo/k8s/llm/valkey.yaml`
  - Verification: `$ uv run devops ci test tests/research/test_inventory.py`
- [x] 1.2 Update the expected line numbers for `k8s/llm/valkey.yaml` in `tests/research/test_inventory.py`
  - Verification: `$ uv run devops ci test tests/research/test_inventory.py`

## 2. Quality Gates

Kind: other.

- [x] 2.1 Verify OpenSpec checks and repository gates pass
  - Verification: `$ uv run devops openspec check`
