# Tasks

## 1. Behavior

- [x] 1.1 Change the Renovate tests: no dry run, no task, empty `allowedCommands`
  - Verification: `$ uv run pytest tests/invariants/test_k8s_renovate.py tests/core/test_renovate_config.py`
- [x] 1.2 Remove `RENOVATE_DRY_RUN`, empty `allowedCommands`, remove the tasks and add the notes
  - Verification: `$ npx --package renovate@44.239.1 renovate-config-validator .github/renovate.json`

## 2. Documents

- [x] 2.1 Update `docs/CLUSTER.md`, the manifest comments and the spec
  - Verification: `$ uv run devops openspec check`
