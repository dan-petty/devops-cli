# Tasks

## 1. Read a config file that a parser cannot load without its text (behavior)

- [x] 1.1 Write the failing tests: the helper, the audit record, the redaction, the round trip and `config unset`.
  Verification: `uv run devops ci test tests/config/test_config_yaml_load_errors.py`
- [x] 1.2 Add `src/devops_cli/config/yaml_errors.py`. Call it from `settings._read_config_file`, `write_history` and `round_trip`, and delete the load-error list and the mark reader of `settings.py`. Update the messages that the tests of the key removal pin.
  Verification: `uv run devops ci test tests/config tests/commands/test_config_audit_keys.py tests/commands/test_config.py`

## 2. Documents (documents)

- [x] 2.1 Point the Safe YAML Parsing section of the PyYAML knowledge base at `load_yaml`.
  Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
