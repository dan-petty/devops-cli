# Tasks

## 1. NetworkPolicy namespace peer correction

- [x] 1.1 Add failing invariant test in `tests/test_k8s_network_policies.py` asserting that every `namespaceSelector` under `k8s/` names a declared or built-in namespace, and verify with `uv run devops ci test tests/test_k8s_network_policies.py`.
- [x] 1.2 Remove the `devops-cli` peer and update the comment in `k8s/llm/portkey/networkpolicy.yaml`, and verify with `uv run devops ci test tests/test_k8s_network_policies.py`.
- [x] 1.3 Remove the `ingress` peer from `k8s/otel/networkpolicy.yaml`, and verify with `uv run devops ci test tests/test_k8s_network_policies.py`.
- [x] 1.4 Run documentation synchronization with `uv run devops docs generate --sync-readme`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
