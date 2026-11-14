# Tasks

## 1. Behavior

- [x] 1.1 Write failing test for the secret-key entry and Helm value mapping
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py -k test_monitoring_grafana_admin_secret_key`
- [x] 1.2 Add secret-key to monitoring/grafana-admin in src/devops_cli/k8s/cluster_secrets.py
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py`
- [x] 1.3 Map GF_SECURITY_SECRET_KEY in k8s/monitoring/grafana-values.yaml
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_manifests.py -k test_every_secret_key_that_a_manifest_reads_from_a_table_secret_is_a_table_entry`

## 2. Documents

- [x] 2.1 Update Cluster Secrets table in k8s/README.md
  - Verification: `$ uv run devops ci docs`
