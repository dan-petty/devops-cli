# Tasks

## 1. Set the flags

Reads: `k8s/llm/gateway/config.yaml` lines 275 to 320, `tests/ai/benchmark/test_k8s_llm_gateway.py` (`_hosted_violations`). Changes: `k8s/llm/gateway/config.yaml`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `k8s/README.md`.

- [x] 1.1 Write the check first: a Claude group without the flags is a violation, and one broken edit proves it. Verify that `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py` fails when the flags are removed from the config
- [x] 1.2 Set `supports_native_structured_output` and `supports_response_schema` in the `model_info` of both Claude groups, and name them in `k8s/README.md`
- [x] 1.3 Verify with `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py tests/invariants/test_k8s_manifests.py tests/docs`

## 2. After the merge

- Pending a person: none. Run `devops roadmap eval stage --model claude-sonnet-5-5 --limit 2` after Argo CD syncs; at least one case stages.
