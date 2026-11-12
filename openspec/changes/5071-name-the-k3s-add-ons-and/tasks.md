# Tasks

## 1. Documents

- [x] 1.1 State in the comment of `k8s/llm/gateway/config.yaml` and the docstring of `check_the_gateway_keeps_its_spend_logs_for_30_days` that the cleanup runs 24 hours after each start of the gateway process
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 In `k8s/README.md`, name the k3s packaged add-ons as the exception to the drift rule, make CoreDNS one case, split its long sentence, remove the reference to #4993, and state the real cleanup time in the Spend logs item
  - Verification: `$ uv run devops ci --check --only docs`
