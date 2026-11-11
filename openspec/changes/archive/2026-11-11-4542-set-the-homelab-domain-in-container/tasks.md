# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests: a Deployment env value with the placeholder gets a test and a replace operation, a value without it and the placeholder in an annotation or an argument get none, and the Argo CD gate allows the placeholder only in the env value
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_argocd_overrides.py tests/k8s/test_k8s_argocd_gate.py`
- [x] 1.2 Extend `_host_fields` with the env values of the containers and init containers of a Deployment
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_argocd_overrides.py tests/k8s/test_k8s_argocd_gate.py`

## 2. Documents

- [x] 2.1 Add the row of the env values to "Homelab Values at Deploy Time" in `k8s/README.md`, and name the Deployment in the paragraph about the patches
  - Verification: `$ uv run devops ci docs`
