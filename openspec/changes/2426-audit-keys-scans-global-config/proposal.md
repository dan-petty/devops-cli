# Proposal

## Why

Issue #2426: `devops config audit-keys` does not scan the global config file `~/.config/devops-cli/config.yaml` when a project config file exists or `DEVOPS_CLI_CONFIG` is set. The audit scans `get_active_config_path()`, which is the one file that a settings save writes. `load_settings` merges two files: the global file and the project file. Thus a plaintext secret in the global file goes into the settings, but the audit reports the config compliant and exits 0. The devcontainer always sets `DEVOPS_CLI_CONFIG`, so there the audit never reads the global file.

## What Changes

- `src/devops_cli/config/settings.py` gets the public function `config_layer_paths()`. It gives the global config file and the project config file, which are the files that `load_settings` merges, in the merge order. `_merged_config_data` reads the files that this function gives, and the error of an unknown key in `load_settings` names lines in these files, so the load and the audit use one rule.
- `audit_keys_cmd` in `src/devops_cli/commands/config.py` scans the files of `config_layer_paths()` in place of `get_active_config_path()`. It also scans `config.yaml` and `.devops/config.yaml` in the current directory, as before.
- The command help, which is the docstring of `audit_keys_cmd`, names the files that the audit scans. `devops docs generate --sync-readme` writes the same text into the generated documents.
- `tests/test_config_audit_keys.py` pins a plaintext secret in the global config file: once with a project file that `DEVOPS_CLI_CONFIG` names, and once with a project file that the directory walk finds.
- The files that the audit scans and its exit code are observable, so the change has a spec delta for the `config-commands` capability.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: adds the requirement that `devops config audit-keys` scans each config file that the settings merge.

## Impact

- `src/devops_cli/config/settings.py`: the new public function `config_layer_paths()`, which `_merged_config_data`, `_read_config_layers` and the error of an unknown key in `load_settings` use. The error path of a config file that is not valid YAML (#1468) does not change.
- `src/devops_cli/commands/config.py`: `audit_keys_cmd` scans the files of `config_layer_paths()`. Its docstring names the scanned files.
- `tests/test_config_audit_keys.py`: one parametrized test for a plaintext secret in the global config file.
- Generated documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/config.md`, `docs/MCP_TOOLS.md`.

## Feasibility

- Confirmed against the source at `origin/main` (e02c3fb0). `audit_keys_cmd` scans `get_active_config_path()`, `Path.cwd() / "config.yaml"` and `Path.cwd() / ".devops" / "config.yaml"`. `get_active_config_path()` returns the file that `DEVOPS_CLI_CONFIG` names, else the project file that the directory walk finds, else `CONFIG_PATH`. `_read_config_layers` reads `CONFIG_PATH` and then merges the project file of `_find_project_config_path()` into it.
- Confirmed with command output on devops-cli 0.9.0 at e02c3fb0. A temporary `HOME` held the key `ai.api_key` with the value `fake-value-0123456789` in `.config/devops-cli/config.yaml`. `DEVOPS_CLI_CONFIG` named a clean file `clean.yaml` (`log_level: INFO`), and the keyring was `keyring.backends.null.Keyring`. `devops config audit-keys --json` exited 0 with `is_compliant: true`, `plaintext_leaks: []` and only `clean.yaml` under `scanned_config_files`. In the same environment, `load_settings().ai.api_key` held the value.
- Confirmed again at `origin/main` daaffc62, after #1468 changed the settings load and #2448 changed `devops config set`. Neither change touched `audit_keys_cmd` or the layers of `_read_config_layers`. On that source, the new test `test_config_audit_keys_fails_on_a_plaintext_secret_in_the_global_config_file` fails in both of its cases with exit code 0, `is_compliant: true`, no leak and one scanned file.

## Existing Tool Considered

The audit reads YAML with PyYAML and finds secret names with the sanitizer of devops-cli (`is_secret_field`), and this change keeps both. No open tool knows which files the settings of devops-cli merge: only `devops_cli.config.settings` knows it. Thus the fix gives that knowledge one public function, and the load and the audit both call it. The change deletes the call of `get_active_config_path()` in `audit_keys_cmd`, which gave the audit a different rule for its files than the load has.
