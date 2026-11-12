# Tasks

## 1. Behavior

- [x] 1.1 Write a failing floor test: a test that starts `kubectl kustomize` or `kubectl patch --local` fails with the process edge message
  - Verification: `$ uv run devops ci test tests/invariants/test_hermetic_floor.py`
- [x] 1.2 Remove the kubectl offline-renderer allowance from the floor in `tests/conftest.py`
  - Verification: `$ uv run devops ci test tests/invariants/test_hermetic_floor.py`

## 2. Tests

- [x] 2.1 Answer `kubectl kustomize` from the tree in the image-pin tests, and the chart output with the committed render
  - Verification: `$ uv run devops ci test tests/k8s/test_image_pins.py`
- [x] 2.2 Fake the lookup of kubectl on PATH in the Argo CD gate tests
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_argocd_gate.py`
- [x] 2.3 Check the shape of the merge patch in the deploy-stack test, with no real kubectl
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py`
- [x] 2.4 Move the Qdrant Secret check to the `k8s` row of `devops ci`
  - Verification: `$ uv run devops ci --check --only k8s`

## 3. Documents

- [x] 3.1 Name the refusal in the docstrings of `tests/support/fakes/openspec.py` and `tests/tools_lock/test_k8s_argo_workflows.py`
  - Verification: `$ uv run devops ci --check --only lint,format,docs,constructs,openspec,test-tree`
