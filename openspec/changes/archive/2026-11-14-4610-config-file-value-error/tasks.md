# Tasks

## 1. Convert a refused config-file value

Reads: `src/devops_cli/config/settings.py`. Changes: the same file, `src/devops_cli/lang/en/errors.py`, and `tests/config/test_config_file_value_errors.py`.

- [x] 1.1 Add `_config_file_error` and call it in `load_settings` after the unknown-key path.
- [x] 1.2 Add the error text.
- [x] 1.3 Add the three tests.
  - Verification: `$ uv run devops ci test tests/config/test_config_file_value_errors.py` passes
