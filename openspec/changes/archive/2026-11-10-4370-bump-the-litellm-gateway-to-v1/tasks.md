# Tasks

## 1. The pin

- [x] 1.1 Write the failing test: the pinned release is not below the release that fixes the advisories, and the exact pin is v1.103.10
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Set the image tag in `k8s/llm/gateway/deployment.yaml`
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py tests/ai/client/test_ai_served_by.py`

## 2. Documents

- [x] 2.1 Update the cost-map text in `k8s/llm/gateway/config.yaml` and `k8s/README.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the merge, check the rollout (`kubectl -n llm rollout status deploy/llm-gateway`), a model call through the gateway and the Jev live check (steps in the pull request comment).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
