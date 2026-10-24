# Tasks

## 1. Field constraints and assignment validation

- [x] 1.1 Write failing tests in `tests/test_config_field_validation.py` for numeric constraints, boolean parsing, and assignment validation, and verify failure with `uv run devops ci test tests/test_config_field_validation.py`
- [x] 1.2 Add field constraints (`gt=0`, `allow_inf_nan=False`) to timeout and duration fields, configure `validate_assignment=True` and `hide_input_in_errors=True` on models, and update `_coerce_setting_value` and `dotted_set` in `src/devops_cli/config/settings.py`
- [x] 1.3 Run `uv run devops ci test tests/test_config_field_validation.py` and verify that the tests pass

## 2. HTTP and service URL type aliases

- [x] 2.1 Write failing tests in `tests/test_config_field_validation.py` for HTTP and service URL aliases and error masking, and verify failure with `uv run devops ci test tests/test_config_field_validation.py`
- [x] 2.2 Implement `HttpUrlStr` and `ServiceUrlStr` aliases, update field types in `src/devops_cli/config/settings.py`, and update `parse_service_url` in `src/devops_cli/k8s/service_proxy.py` to state reasons without embedding URLs
- [x] 2.3 Run `uv run devops ci test tests/test_config_field_validation.py tests/test_k8s_service_proxy.py` and verify that the tests pass

## 3. CLI commands, telemetry fail-closed, and documentation synchronization

- [x] 3.1 Write failing tests for `devops config set` and `devops ai config` exit codes on invalid values and telemetry fail-closed behavior, and verify failure with `uv run devops ci test tests/test_config_field_validation.py tests/test_config_env_overrides.py`
- [x] 3.2 Update `commands/config.py`, `commands/ai.py`, `commands/k8s/networking.py`, and `telemetry/tracer.py` to handle validation errors and preserve fail-closed behavior
- [x] 3.3 Run `uv run devops docs generate --sync-readme` and verify `uv run devops docs check` and `uv run devops openspec check` pass

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
- Pending a person: verify workstation configuration files with `devops config show`.
