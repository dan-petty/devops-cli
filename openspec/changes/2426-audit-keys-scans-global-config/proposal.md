# Proposal

## Why

Issue #2426: `devops config audit-keys` does not scan the global config file `~/.config/devops-cli/config.yaml` when a project config file exists or `DEVOPS_CLI_CONFIG` is set. The audit scans `get_active_config_path()`, which is the one file that a settings save writes. `load_settings` merges two files: the global file and the project file. Thus a plaintext secret in the global file goes into the settings, but the audit reports the config compliant and exits 0. The devcontainer always sets `DEVOPS_CLI_CONFIG`, so there the audit never reads the global file.

## What Changes

- `src/devops_cli/config/settings.py` gets the public function `config_layer_paths()`. It gives the global config file and the project config file, in the merge order. These are the files that `load_settings` merges. `_merged_config_data` reads the files of this function. The error of an unknown key in `load_settings` names lines in the same files. Thus the load and the audit use one rule.
- `audit_keys_cmd` in `src/devops_cli/commands/config.py` scans the files of `config_layer_paths()` in place of `get_active_config_path()`. It also scans `config.yaml` and `.devops/config.yaml` in the current directory, as before.
- The audit refuses each error of the YAML loader that the settings load refuses (`_YAML_LOAD_ERRORS`, #1468). It reports the file unaudited and shows no text of the file. Before, a value such as `!!bool <text>` stopped the audit with the value in its output.
- A leak names the full path of its file (`<path>:<section>.<key>`). The global file and a project file can both have the name `config.yaml`.
- The command help, which is the docstring of `audit_keys_cmd`, names the files that the audit scans. `devops docs generate --sync-readme` writes the same text into the generated documents.
- `tests/test_config_audit_keys.py` writes a plaintext secret into the global config file of the isolated HOME. The project file is the file that `DEVOPS_CLI_CONFIG` names, or the file that the directory walk finds. The tests also put a file that the YAML loader cannot load into the global config file.
- The files that the audit scans, the text of a leak and the exit code are observable. Thus the change has a spec delta for the `config-commands` capability.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: adds three requirements for `devops config audit-keys`. It scans each config file that the settings merge. A leak names the full path of its file. The audit quotes no text of a config file that it cannot load.

## Impact

- `src/devops_cli/config/settings.py`: the new public function `config_layer_paths()`, which `_merged_config_data`, `_read_config_layers` and the error of an unknown key in `load_settings` use. The error path of a config file that is not valid YAML (#1468) does not change.
- `src/devops_cli/commands/config.py`: `audit_keys_cmd` scans the files of `config_layer_paths()`. Its docstring names the scanned files. `_scan_yaml_for_secret_keys` catches `_YAML_LOAD_ERRORS` and names the full path of the file in each leak.
- `tests/test_config_audit_keys.py`: tests for a plaintext secret in the global config file, in the JSON report and in the table. A test for a global config file that the YAML loader cannot load. The tests that pin the text of a leak expect the full path.
- Generated documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/config.md`, `docs/MCP_TOOLS.md`.

## Feasibility

- Confirmed against the source at `origin/main` (e02c3fb0). `audit_keys_cmd` scans `get_active_config_path()`, `Path.cwd() / "config.yaml"` and `Path.cwd() / ".devops" / "config.yaml"`. `get_active_config_path()` returns the file that `DEVOPS_CLI_CONFIG` names, else the project file that the directory walk finds, else `CONFIG_PATH`. `_read_config_layers` reads `CONFIG_PATH` and then merges the project file of `_find_project_config_path()` into it.
- Confirmed with command output on devops-cli 0.9.0 at e02c3fb0. A temporary `HOME` held the key `ai.api_key` with the value `fake-value-0123456789` in `.config/devops-cli/config.yaml`. `DEVOPS_CLI_CONFIG` named a clean file `clean.yaml` (`log_level: INFO`), and the keyring was `keyring.backends.null.Keyring`. `devops config audit-keys --json` exited 0 with `is_compliant: true`, `plaintext_leaks: []` and only `clean.yaml` under `scanned_config_files`. In the same environment, `load_settings().ai.api_key` held the value.
- Confirmed again at `origin/main` daaffc62, after #1468 changed the settings load and #2448 changed `devops config set`. Neither change touched `audit_keys_cmd` or the layers of `_read_config_layers`. On that source, the new test `test_config_audit_keys_fails_on_a_plaintext_secret_in_the_global_config_file` fails in both of its cases with exit code 0, `is_compliant: true`, no leak and one scanned file.
- Confirmed with a probe of the scanner on this branch, before decision 4 of design.md. For a file that holds `ai:` and `  api_key: !!bool FAKE-SECRET-0123`, `_scan_yaml_for_secret_keys` raised `KeyError: 'fake-secret-0123'`. The test `test_config_audit_keys_reports_a_global_config_file_that_the_yaml_loader_cannot_load_unaudited` failed in four of its six cases before the fix: `KeyError`, `AttributeError`, `IndexError` and `RecursionError`.

## Existing Tool Considered

The audit reads YAML with PyYAML and finds secret names with the sanitizer of devops-cli (`is_secret_field`), and this change keeps both. No open tool knows which files the settings of devops-cli merge: only `devops_cli.config.settings` knows it. Thus the fix gives that knowledge one public function, and the load and the audit both call it. The change deletes the call of `get_active_config_path()` in `audit_keys_cmd`, which gave the audit a different rule for its files than the load has. The scanner also uses the error types of the load (`_YAML_LOAD_ERRORS`) and its position text (`_yaml_error_location`), in place of its own copy.
