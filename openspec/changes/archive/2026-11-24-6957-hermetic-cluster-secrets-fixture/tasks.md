# Tasks

## 1. Behavior

- [x] 1.1 Update `tests/k8s/test_cluster_secrets_file.py` to test fixture resolution hermetically
  - Verification: `$ uv run pytest tests/k8s/test_cluster_secrets_file.py -k test_resolve_fixture_secrets_file_variants`
- [x] 1.2 Fix fallback condition in `src/devops_cli/k8s/cluster_secrets.py`
  - Verification: `$ uv run pytest tests/k8s/test_cluster_secrets_file.py`

## 2. Verification

- [x] 2.1 Run CI quality gate
  - Verification: `$ uv run devops ci --check --only test,lint,typecheck,k8s`

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
