# Tasks

## 1. A plaintext secret fails the audit

- [x] 1.1 Replace `test_config_audit_keys_plaintext_leak_detected` in `tests/test_config_audit_keys.py` with `test_config_audit_keys_fails_on_a_plaintext_secret_in_the_table` and `test_config_audit_keys_fails_on_a_plaintext_secret_in_the_json_report`, which expect exit 1, the leak in the report and no success line, verified to fail on `origin/main` with `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Make `audit_keys_cmd` in `src/devops_cli/commands/config.py` exit 1 in each output branch when the audit is not compliant, and print the success line only when it is compliant, verified with `uv run devops ci test tests/test_config_audit_keys.py tests/test_zero_plaintext_invariants.py`
- [x] 1.3 State the exit codes in the docstring of `audit_keys_cmd`, and regenerate the documents with `uv run devops docs generate --sync-readme`, verified with `uv run devops docs check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
