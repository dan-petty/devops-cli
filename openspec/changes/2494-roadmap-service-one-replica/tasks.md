# Tasks

## 1. Manifests and documents

- [x] Expect `replicas: 1` in `tests/test_k8s_roadmap_service.py`, expect `ai.max_retries` 1 in the template test of `tests/test_k8s_devops_runtime.py`, and add a test to `tests/test_k8s_configmap.py` that renders the repository's template; see the three tests fail
  - Verification: `uv run devops ci test tests/test_k8s_roadmap_service.py tests/test_k8s_devops_runtime.py tests/test_k8s_configmap.py`
- [x] Set `replicas: 1` in `k8s/devops/roadmap-service/deployment.yaml`, with a comment that names the App and points to the stop switch, and set `ai.max_retries: 1` in `k8s/devops/configmap.example.yaml`
  - Verification: `uv run devops ci test tests/test_k8s_roadmap_service.py tests/test_k8s_devops_runtime.py tests/test_k8s_configmap.py tests/test_k8s_llm_gateway.py`
- [x] In `k8s/README.md`, replace the hold note of "Roadmap service" with the go-live check and the stop switch, and name the template's retry count in "LLM Gateway"; remove the hold from the docstring in `tests/test_k8s.py`
  - Verification: `uv run devops ci test tests/test_k8s.py tests/test_docs.py tests/test_docs_inventory.py && uv run devops docs check`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2494-roadmap-service-one-replica`
- Pending a person: set each managed repository's webhook to the Issues event only (`k8s/README.md`, Roadmap service, step 8).
- Pending a person: after Argo CD syncs the deployment, do the go-live check in `k8s/README.md`, Roadmap service.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
