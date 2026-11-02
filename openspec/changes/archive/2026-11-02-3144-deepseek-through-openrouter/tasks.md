# Tasks

## 1. Route, key and docs

Reads: `k8s/llm/gateway/config.yaml`, `k8s/llm/gateway/deployment.yaml`, `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/config/env.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`. Changes: the same files, `tests/ai/test_k8s_gpu_matrix.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/commands/test_config_audit_keys.py`, `tests/security/test_config_declarations.py`, `k8s/README.md`, `SECURITY.md`, `docs/ENV_VARS.md`.

- [x] 1.1 Add the group to `HOSTED_GROUPS` and the provider `openrouter` to the hosted-group check first. Verify that `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py` fails before the manifests change
- [x] 1.2 Add the group, the Deployment variable, the Secret entry and the credential
- [x] 1.3 Update the secret table, the key lists, the model count, the README and rule 12 of SECURITY.md, and run `uv run devops docs generate --sync-readme`
- [x] 1.4 Verify with `uv run devops ci test tests/ai tests/k8s tests/invariants tests/config tests/docs tests/commands tests/security`

## 2. After the merge

- Pending a person: store the key with `devops config set openrouter.api_key`, run `devops k8s push-secrets --only llm/llm-gateway-secrets`, and call the group once with the `curl` command in `k8s/README.md`.
