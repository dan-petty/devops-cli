# Tasks

## 1. The managed-tool bootstrap has no test switch

- [x] Move the tests that run `post-create` onto `--skip-tools` and `skip_tools=True`, and the two `run-lifecycle` tests onto the locked tools at their pins with `link_every_tool_at_pin` from `tests/support/tools.py`
  - Verification: `uv run devops ci test tests/test_devcontainer.py tests/test_install_tools.py`
- [x] Delete the variable check in `_bootstrap_managed_tools`, the fixture's `setenv`, and the unit-test case of the variable
  - Verification: `git grep -n DEVOPS_CLI_SKIP_TOOL_BOOTSTRAP -- src tests` prints nothing
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1729-skip-tool-bootstrap-switch`

## Workflow follow-up

- #1336 bans the test switches in `src/` with a tool.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
