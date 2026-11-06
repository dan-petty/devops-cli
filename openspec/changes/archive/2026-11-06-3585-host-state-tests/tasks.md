# Tasks

## 1. Project config search stops at a project root
- [x] 1.1 Add `project_config_directories` and use it in `_find_project_config_path` and in the SSH key prefix search; add the tests of the root rule
  - Verification: `uv run devops ci test tests/telemetry/test_config_env_overrides.py tests/crypto/test_ssh.py`

## 2. Tests that read the state of the host
- [x] 2.1 Give the install-tools status test an empty target directory and an empty PATH, and add the test of the pinned devcontainer CLI
  - Verification: `uv run devops ci test tests/commands/test_devcontainer_install_tools_dry_run.py`
- [x] 2.2 Give the direct-executor network-profile case a Popeye stand-in
  - Verification: `uv run devops ci test tests/ai/test_tool_executor_contract.py`

## Workflow follow-up
- The pytest time of the gate is in #3593 and is not in this change.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
