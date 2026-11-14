# Tasks

## 1. Behavior

- [x] 1.1 Write failing test for dev sandbox and MCP server in grafana-values.yaml
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py -k test_grafana_provisions_the_llm_app_for_litellm_gateway`
- [x] 1.2 Enable dev sandbox and MCP server in grafana-values.yaml
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py`

## 2. Documents

- [x] 2.1 Update Grafana LLM Plugin section in k8s/README.md
  - Verification: `$ uv run devops ci docs`
