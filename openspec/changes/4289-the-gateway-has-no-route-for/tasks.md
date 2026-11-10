# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests: the client path is a pass-through of the gateway, and the gateway lists no chat route for Jev
  - Verification: `$ uv run devops ci test tests/ai/test_jev_gateway_route.py`
- [x] 1.2 Add the pass-through `POST /v1/systemone` to `k8s/llm/gateway/config.yaml`, and remove the chat route `typesafe/jev-1.14` from `model_list`, `CONST_AI_GATEWAY_HOSTED_MODELS` and the gateway test
  - Verification: `$ uv run devops ci test tests/ai/test_jev_gateway_route.py tests/ai/test_jev.py tests/ai/benchmark/test_k8s_llm_gateway.py tests/config/test_settings.py tests/config/test_k8s_devops_runtime.py tests/ai/test_k8s_gpu_matrix.py`

## 2. Documents

- [x] 2.1 Name the route, the key and the live check in `k8s/README.md` and `SECURITY.md` rule 13
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
- Pending a person: run the live check of the pull request comment after Argo CD rolls the gateway.
