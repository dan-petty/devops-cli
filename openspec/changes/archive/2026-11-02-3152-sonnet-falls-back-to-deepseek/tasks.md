# Tasks

## 1. Add the fallback

Reads: `k8s/llm/gateway/config.yaml` lines 300 to 330, `tests/ai/benchmark/test_k8s_llm_gateway.py` (`_hosted_violations`). Changes: `k8s/llm/gateway/config.yaml`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `k8s/README.md`, `SECURITY.md`.

- [x] 1.1 Change the hosted-group check first: a fallback from a group that is not hosted to a hosted group is a violation, and a hosted-to-hosted fallback is not. Verify that `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py` passes with the real config and fails for the broken edit
- [x] 1.2 Add the fallback to the config, and describe it in the README and in rule 12 of SECURITY.md
- [x] 1.3 Verify with `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py tests/invariants/test_k8s_manifests.py tests/docs`

## 2. After the merge

- Pending a person: none. To see the fallback work, stop the Anthropic key on purpose (a Secret with a wrong `anthropic-api-key`) and call `claude-sonnet-5-5` once; the answer comes from the DeepSeek group.
