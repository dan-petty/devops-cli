# Tasks

## 1. Delete the tests that read the clock

Kind: other. Reads: `tests/support/trivyignore.py`. Changes: `tests/invariants/test_mcp_server_image.py`, `tests/invariants/test_runner_image.py`, `tests/invariants/test_service_image.py`, `tests/gate/tree_checks/config_reads.toml`.

- [ ] 1.1 Delete the test of `.trivyignore-mcp-server` in `tests/invariants/test_mcp_server_image.py`, the test of `.trivyignore-tofu` in `tests/invariants/test_runner_image.py` and the test of `.trivyignore` in `tests/invariants/test_service_image.py`. Remove the imports that only they used.
  - Verification: `$ ! git grep -n 'datetime.now' -- tests/invariants/test_mcp_server_image.py tests/invariants/test_runner_image.py tests/invariants/test_service_image.py`
- [ ] 1.2 Lower the counts of the three modules in `tests/gate/tree_checks/config_reads.toml` by one each.
  - Verification: `$ uv run devops ci --check --only test-tree`
- [ ] 1.3 Run the tests of the three modules.
  - Verification: `$ uv run devops ci test tests/invariants/test_mcp_server_image.py tests/invariants/test_runner_image.py tests/invariants/test_service_image.py`
