# Tasks

## 1. Return the loaded settings from the config route

Kind: behavior. Reads: `src/devops_cli/server/routes/workspace.py`, `tests/server/test_server.py`. Changes: `src/devops_cli/server/routes/workspace.py`, `tests/server/test_server.py`.

- [x] 1.1 Add `test_config_endpoint_reflects_environment_variable`, `test_config_endpoint_reflects_config_file` and `test_config_endpoint_redacts_a_loaded_secret` to `tests/server/test_server.py`, and watch them fail on the base
  - Verification: `$ uv run devops ci test tests/server/test_server.py -k config_endpoint`
- [x] 1.2 Call `load_settings()` in `get_configuration` and import it in place of `Settings`
  - Verification: `$ uv run devops ci test tests/server/test_server.py -k config_endpoint`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
