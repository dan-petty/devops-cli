# Tasks

## 1. Reference models in the template

Reads: `k8s/devops/configmap.example.yaml`, `src/devops_cli/k8s/configmap.py`. Changes: `k8s/devops/configmap.example.yaml`, `tests/k8s/test_k8s_configmap.py`.

- [x] 1.1 Write the two tests that render the template and read the comment above `reference_model`, and watch them fail on origin/main
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap.py` fails on the base
- [x] 1.2 Add `ai.reference_model` and `ai.reference_embedding_model` and their comment to the template
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap.py` passes
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap_keys.py` passes

## 2. Documents

Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [x] 2.1 Tell the two settings, the prices and the place of the prices in item 19 of `k8s/README.md`
  - Verification: `$ git grep -n "reference_embedding_model: qwen/qwen3-embedding-8b" -- k8s/README.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- A repository-owned price (a setting that `PricingRegistry` reads) is #4242.
