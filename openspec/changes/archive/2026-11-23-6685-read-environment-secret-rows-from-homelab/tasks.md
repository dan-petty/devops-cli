# Tasks

## 1. Behavior

- [x] 1.1 Write failing test
  - Verification: `$ uv run pytest tests/k8s/test_cluster_secrets_file.py tests/k8s/test_cluster_secret_source.py`
- [x] 1.2 Implement the TOML loader and file model
  - Verification: `$ uv run pytest tests/k8s/test_cluster_secrets_file.py`
- [x] 1.3 Remove moved environment rows from cluster_secrets.py
  - Verification: `$ uv run pytest tests/k8s/test_cluster_secret_source.py`
- [x] 1.4 Wire readers to load environment rows from cluster-secrets.toml
  - Verification: `$ uv run pytest tests/k8s -q -k cluster_secret`

## 2. Verification

- [x] 2.1 Run scoped CI checks
  - Verification: `$ uv run devops ci --check --only test,lint,typecheck`
