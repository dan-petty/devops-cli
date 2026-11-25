# Tasks

## 1. Behavior

- [x] 1.1 Write failing test
  - Verification: `$ uv run devops ci test tests/invariants/test_dev_only_imports.py`
- [x] 1.2 Move the spec model to `grafana/service_specs.py`
  - Verification: `$ uv run devops ci test tests/invariants/test_dev_only_imports.py tests/grafana tests/k8s/test_k8s_catalog.py`

## 2. Documents

- [x] 2.1 Spec delta of `mcp-server-image`; no user document changes
  - Verification: `$ uv run devops openspec check`
