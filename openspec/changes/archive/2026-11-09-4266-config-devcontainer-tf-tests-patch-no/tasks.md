# Tasks

## 1. Config and Workspace Command Tests

- [x] 1.1 Remove internal patches from `tests/commands/test_config_commands.py`
  - Verification: `uv run pytest tests/commands/test_config_commands.py`
- [x] 1.2 Remove internal patches from `tests/commands/test_workspace.py`
  - Verification: `uv run pytest tests/commands/test_workspace.py`

## 2. Devcontainer and Terraform Command Tests

- [x] 2.1 Remove internal patches from `tests/commands/test_devcontainer.py`
  - Verification: `uv run pytest tests/commands/test_devcontainer.py`
- [x] 2.2 Remove internal patches from `tests/commands/test_tf.py`
  - Verification: `uv run pytest tests/commands/test_tf.py`

## 3. Test Runner and Kubernetes Mattermost Bootstrap Command Tests

- [x] 3.1 Remove internal patches from `tests/commands/test_test_runner.py`
  - Verification: `uv run pytest tests/commands/test_test_runner.py`
- [x] 3.2 Remove internal patches from `tests/commands/test_k8s_bootstrap_mattermost.py`
  - Verification: `uv run pytest tests/commands/test_k8s_bootstrap_mattermost.py`

## 4. Verification and Quality Gates

- [x] 4.1 Verify zero devops_cli internal patches across all 6 target files
  - Verification: `git grep -n -E "(monkeypatch\.setattr|patch(\.object)?)\(.*['\"]devops_cli" tests/commands/test_config_commands.py tests/commands/test_workspace.py tests/commands/test_devcontainer.py tests/commands/test_tf.py tests/commands/test_test_runner.py tests/commands/test_k8s_bootstrap_mattermost.py`
- [x] 4.2 Run full test suite for the 6 files and quality checks
  - Verification: `uv run pytest tests/commands/test_config_commands.py tests/commands/test_workspace.py tests/commands/test_devcontainer.py tests/commands/test_tf.py tests/commands/test_test_runner.py tests/commands/test_k8s_bootstrap_mattermost.py`
- [x] 4.3 Archive OpenSpec change folder and run pre-push static checks
  - Verification: `uv run devops openspec archive 4266-config-devcontainer-tf-tests-patch-no && uv run ruff check && uv run ruff format --check`
