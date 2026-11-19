# Tasks

## 1. ConfigMap template

- [x] 1.1 Set `roadmap.stage.gate_returns` 8, `backlog_interval_minutes` 4 and `backlog_threshold` 10, and add `ai.tasks.fix_checks` with the DeepSeek group and a 256,000-token window, in `k8s/devops/configmap.example.yaml`
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 Correct the comments on the local-model rule, the 256,000-token window, `roadmap.stage.limit`, `roadmap.mcp` and the old images
  - Verification: `$ uv run devops ci --check --only docs`

## 2. Proof

- [x] 2.1 Load the template data and its render through the settings model, and compare the render with the live ConfigMap
  - Verification: `$ uv run devops ci --check --only openspec`
