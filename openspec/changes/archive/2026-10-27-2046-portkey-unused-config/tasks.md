# Tasks

## 1. Portkey Gateway Unused ConfigMap Removal

- [x] Add failing test in `tests/test_ai_gateway_portkey.py` asserting `configmap.yaml` does not exist and `deployment.yaml` has no config volume
  - Verification: `uv run pytest tests/test_ai_gateway_portkey.py -k test_portkey_manifests_have_no_unused_configmap`
- [x] Remove `k8s/llm/portkey/configmap.yaml`
- [x] Remove `config-volume` mount and volume from `k8s/llm/portkey/deployment.yaml`
- [x] Remove `portkey/configmap.yaml` from `k8s/llm/kustomization.yaml` and `src/devops_cli/commands/k8s/stack_lifecycle.py`
- [x] Remove the obsolete `test_portkey_coder_targets_ollama_served_model` test from `tests/test_ai_gateway_portkey.py`
- [x] Verify tests pass and run fail-to-pass check
  - Verification: `uv run devops ci test tests/test_ai_gateway_portkey.py`
- [x] Archive OpenSpec change
  - Verification: `uv run devops openspec archive 2046-portkey-unused-config`
