# Tasks

## 1. Behavior

- [x] 1.1 Add test for installed package fixture resolution in `tests/k8s/test_cluster_secrets_file.py`
  - Verification: `$ uv run pytest tests/k8s/test_cluster_secrets_file.py -k test_load_cluster_secrets_table_resolves_fixture_when_installed_in_site_packages`
- [x] 1.2 Implement repository fixture resolution in `src/devops_cli/k8s/environment.py` and `src/devops_cli/k8s/cluster_secrets.py`
  - Verification: `$ uv run pytest tests/k8s/test_cluster_secrets_file.py`

## 2. Verification

- [x] 2.1 Run CI quality gates
  - Verification: `$ uv run devops ci --check --only test,lint,typecheck,k8s`
