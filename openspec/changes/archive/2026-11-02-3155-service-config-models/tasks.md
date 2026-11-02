# Tasks

## 1. Record the Service models

Reads: `k8s/devops/configmap.example.yaml`, `k8s/README.md` item 18, `tests/config/test_k8s_devops_runtime.py` lines 150 to 185. Changes: the same files and `tests/ai/benchmark/test_k8s_llm_gateway.py`.

This group changes an example and a document. The tests hold the example against the settings model and the gateway groups.

- [x] 1.1 Change the example config and the test of it, and add the test that every model of the example is a gateway group. Verify that `uv run devops ci test tests/config/test_k8s_devops_runtime.py tests/ai/benchmark/test_k8s_llm_gateway.py` passes
- [x] 1.2 Add item 19 to the Roadmap service section of `k8s/README.md`, and verify that `uv run devops ci test tests/docs tests/invariants/test_k8s_manifests.py` passes
