# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for grafana-llm-app provisioning and secret entry
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py -k test_grafana_provisions_the_llm_app_for_litellm_gateway`
- [x] 1.2 Add llm-gateway-key to monitoring/grafana-admin in src/devops_cli/k8s/cluster_secrets.py and update secret tests
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py`
- [x] 1.3 Add extraConfigmapMounts, extraObjects, and GF_LLM_GATEWAY_KEY in k8s/monitoring/grafana-values.yaml
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py`

## 2. Documents

- [x] 2.1 Update Grafana LLM Plugin section in k8s/README.md
  - Verification: `$ uv run devops ci docs`
