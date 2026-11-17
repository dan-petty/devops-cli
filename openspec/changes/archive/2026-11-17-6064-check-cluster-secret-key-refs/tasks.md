# Tasks

## 1. Behavior

- [x] 1.1 Implement `check_secret_key_refs` in `src/devops_cli/k8s/cluster_secrets.py`
  - Verification: `$ uv run pytest tests/k8s/test_cluster_secret_key_refs.py`
- [x] 1.2 Add tests in `tests/k8s/test_cluster_secret_key_refs.py`
  - Verification: `$ uv run pytest tests/k8s/test_cluster_secret_key_refs.py`
- [x] 1.3 Add gate check in `tests/gate/k8s_checks/cluster_secrets.py`
  - Verification: `$ uv run python -m tests.gate.k8s`

## 2. Documents

- [x] 2.1 Update Cluster Secrets section in `k8s/README.md` with live plan check instructions
  - Verification: `$ uv run devops ci docs`
