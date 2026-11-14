# Tasks

## 1. Bound the test row and the index build

Reads: `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`. Changes: the same files, the workflow, the document, and the tests.

- [x] 1.1 Add `timeout_seconds` to `CheckSpec` and use it in the runner.
- [x] 1.2 Set 900 s in `_with_test_shard` and 3600 s for the index build.
- [x] 1.3 Wrap the Service Image Tests `docker run` in `timeout --kill-after=30 900`.
- [x] 1.4 Update `docs/TESTING.md` and add the two tests.
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py tests/invariants/test_workflow_contracts.py` passes
