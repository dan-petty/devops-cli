# Tasks

## 1. Documentation & Runbook

- [x] 1.1 Add `Local-Path Retain Migration` section to `k8s/README.md`
  - Verification: `$ uv run devops ci --check --only docs`

## 2. Test Verification

- [x] 2.1 Add `tests/k8s/test_k8s_retain_migration_docs.py`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_retain_migration_docs.py`

## 3. Quality Gate

- [x] 3.1 Run local quality gate checks
  - Verification: `$ uv run devops openspec check`
