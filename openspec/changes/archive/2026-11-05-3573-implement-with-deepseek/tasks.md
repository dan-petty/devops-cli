# Tasks

## 1. The template and its test

Kind: behavior. Reads: `k8s/llm/gateway/config.yaml`, `src/devops_cli/config/settings.py`. Changes: `k8s/devops/configmap.example.yaml`, `tests/config/test_k8s_devops_runtime.py`.

- [x] 1.1 Add the test that holds the implement model, the ladder tiers and the window of the example ConfigMap to the gateway config.
  - Verification: `uv run devops ci test tests/config/test_k8s_devops_runtime.py`
- [x] 1.2 Set `ai.tasks.implement` and `roadmap.implement.ladder` in the example ConfigMap.
  - Verification: `uv run devops ci test tests/config/test_k8s_devops_runtime.py tests/server/routes/test_k8s_roadmap_service.py tests/k8s/test_k8s_configmap.py`

## 2. Documents

Kind: documents. Changes: `k8s/README.md`, `docs/roadmap/implement.md`, `SECURITY.md`.

- [x] 2.1 State the routing, the window, the cost and the egress of the implement prompts.
  - Verification: `uv run devops ci docs`

## 3. Archive

Kind: documents.

- [x] 3.1 Archive the change with `uv run devops openspec archive 3573-implement-with-deepseek`.

## Workflow follow-up

- Pending a person: run `devops k8s deploy-stack --stack devops` from a checkout of `main`, then `kubectl -n devops rollout restart deployment/roadmap-service`. A merge alone does not apply the ConfigMap.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
