# Tasks

## 1. Behavior

- [x] 1.1 Change the tests of the kustomizations of `deploy-stack` and see them fail
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py`
- [x] 1.2 Remove the folder from `KUSTOMIZATIONS_BY_STACK`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py`

## 2. Documents

- [x] 2.1 Correct the comment of the GPU label constants
  - Verification: `$ uv run devops ci docs`
