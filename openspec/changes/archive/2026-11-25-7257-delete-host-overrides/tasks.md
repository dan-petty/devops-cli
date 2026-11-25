# Tasks

## 1. Behavior

- [x] 1.1 Change the tests of `deploy-stack` on a cluster that Argo CD manages and see them fail
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py`
- [x] 1.2 Delete the override path and move the host field rule into the gate
  - Verification: `$ uv run devops ci test tests/commands/k8s`

## 2. Documents

- [x] 2.1 Update `k8s/README.md` and the generated references
  - Verification: `$ uv run devops ci docs`
