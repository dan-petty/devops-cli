# Task: The secrets audit never prints a config line it cannot parse, and an unparsable file is not reported clean (#1022)

**Issue**: [#1022](https://github.com/dan-petty/devops-cli/issues/1022)
**Status**: Done
**Milestone**: v0.2.30
**Priority**: priority/p2-medium
**Scope**: type/security, scope/security, scope/config

## Description
`devops config audit-keys` logged PyYAML's error message when a config file did not parse. That message quotes the offending line, so a malformed `api_key: <value>: x` line printed the value to stderr, and the audit then reported the file clean and exited 0.

- `_scan_yaml_for_secret_keys` (`src/devops_cli/commands/config.py`) returns `None` for a file it cannot read or parse, including a value PyYAML resolves but cannot build (an impossible date, an integer past Python's digit limit), which raises a plain `ValueError`. Its warning, `Could not audit config file <path>: <error class> at line L, column C`, takes the position from `problem_mark` when the error is a `yaml.MarkedYAMLError` and names no position otherwise (`OSError`, a `ValueError` such as `UnicodeDecodeError`, `ReaderError`). It never logs the error, its mark, `problem` or `context`, all of which can quote the file. The wording keeps the secret/token/password words out of the format string, so Semgrep's `python-logger-credential-disclosure` rule no longer matches the line.
- `_detect_keyring_secret_leaks` returns the leaks and the unaudited files.
- `audit_keys_cmd` shows `UNAUDITED` in the Zero-Plaintext Check and Compliance columns while any file is unaudited, lists the files under `unaudited_config_files` in `--json`, marks every key and the report not compliant, prints the paths (never their content) and exits 1. It prints the success line only when there is no leak and no unaudited file. The MCP `config_audit_keys` tool needs no change: the non-zero exit becomes a tool error.

## Acceptance Criteria
- [x] The parse-failure log carries the file, the error class and the line and column, never the error message or the snippet: `test_config_audit_keys_never_logs_an_unparsable_line` (`tests/test_config_audit_keys.py`) asserts `FAKE-1022-value` is in neither the output, stderr nor any log record, and that one record names the file, `ScannerError` and `line 2, column 27`.
- [x] A file the audit cannot read or parse is reported unaudited, not clean, and the command exits 1: `test_config_audit_keys_reports_an_unparsable_file_unaudited` (table, no `CLEAN (0 Plaintext)` and no success line), `test_config_audit_keys_reports_an_undecodable_file_unaudited` (a non-UTF-8 file, logged with its error class and no position) and `test_config_audit_keys_reports_an_unconstructable_value_unaudited` (an impossible date).
- [x] `--json` lists unaudited files separately from leaks: `test_config_audit_keys_json_lists_unaudited_files_apart_from_leaks`.
- [x] Tests run offline in tmp directories: the module's autouse `_audit_in_tmp_dir` fixture runs every audit in `tmp_path`, so a developer's own `config.yaml` is never scanned, and the tests only read and write files.
- [x] `changelog.d/1022.md` records the fix under `### Security`; `CHANGELOG.md` is not edited.
- [x] `uv run devops ci` passes: the PR's passing checks.

## Deliverables
- [x] `src/devops_cli/commands/config.py`: the scan, the detector's `(leaks, unaudited)` result and the command's unaudited report and exit code.
- [x] `tests/test_config_audit_keys.py` and `tests/test_zero_plaintext_invariants.py` (the detector's callers unpack the tuple; the workspace scan also asserts no unaudited file).
- [x] `docs/commands/config.md`, `docs/CLI_REFERENCE.md` and the README command row, regenerated for the help's exit-code sentence.
- `config/settings.py::_read_config_layers` lets a `yaml.YAMLError`, whose message quotes the line, propagate from any command that loads settings: moved to #1468.
- A confirmed plaintext leak still exits 0, as `test_config_audit_keys_plaintext_leak_detected` pins: moved to #1469.
