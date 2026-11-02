# Tasks

## 1. Route, key and egress

Reads: `k8s/llm/gateway/config.yaml`, `k8s/llm/gateway/deployment.yaml`, `k8s/llm/gateway/networkpolicy.yaml`, `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/config/env.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`. Changes: the same files, `tests/ai/test_k8s_gpu_matrix.py`, `tests/k8s/test_cluster_secret_plan.py`, `k8s/README.md`, `SECURITY.md`, `docs/ENV_VARS.md`.

- [x] 1.1 Write the tests first: the hosted-group rules and their six broken edits, and the egress rule with its four new widening edits. Verify that `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py` fails before the manifests change
- [x] 1.2 Add the three groups to the gateway config, the two optional key variables to the Deployment, and the egress rule to the NetworkPolicy
- [x] 1.3 Add the two optional Secret entries and the two credentials, and update the expected secret table and the README table
- [x] 1.4 Document the groups in `k8s/README.md` and rule 12 in `SECURITY.md`, and run `uv run devops docs generate --sync-readme`
- [x] 1.5 Verify with `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py tests/ai/test_k8s_gpu_matrix.py tests/k8s tests/invariants/test_k8s_manifests.py tests/config tests/docs`

## 2. Prove the config with LiteLLM

- [x] 2.1 In a scratch environment with `litellm==1.103.0`, build a `Router` from the three groups with no key set, and see it start. Call each group with a mocked reply and see the cost that the prices predict
- [x] 2.2 Send a call with `temperature` and `top_p` to a Claude group with a transport spy, and see that the request body holds neither

## 3. After the merge

- Pending a person: store the keys with `devops config set gemini.api_key` and `devops config set anthropic.api_key`, run `devops k8s push-secrets --only llm/llm-gateway-secrets`, and call each group once with the `curl` command in `k8s/README.md`. A call that answers proves the key, the egress rule and the model name.
