# Design

## Context

See proposal.md for the background. `load_settings` merges the global config file and the project config file (`_read_config_layers`). `audit_keys_cmd` scans `get_active_config_path()`, which is one of these two files, and `config.yaml` and `.devops/config.yaml` in the current directory. When a project file exists, the audit does not scan the global file.

## Goals / Non-Goals

**Goals:**
- Make the audit scan each config file that the settings merge.
- Give the load and the audit one rule for these files, so that they cannot become different again.
- Make the report of the audit tell which file holds a leak, and show no text of a file that the audit cannot load.

**Non-Goals:**
- Change how the audit finds a plaintext secret. A secret under a key with more than two levels, such as `service.github_app.private_key`, is #2511.
- Change the file that a settings save writes (`get_active_config_path()`), or the file that `devops config unset` edits. A command that removes a plaintext secret from a file that is not the active file is #2513.
- Change the error of a config file that is not valid YAML in the settings load (#1468, `_read_config_file`).

## Decisions

### 1. One public function gives the files that the settings merge
- Decision: `config_layer_paths()` in `src/devops_cli/config/settings.py` gives the global file and the project file (or `None`), in the merge order. `_merged_config_data` gets its files from this function and gives them to `_read_config_layers`. The error of an unknown key in `load_settings` (#2201) gets the same files from it. `audit_keys_cmd` scans each file of the function that is not `None`.
- Rationale: The defect is that the audit has its own rule for the files of the settings. With one function, a new layer of the load is also a file of the audit.
- Alternative considered: Add `CONFIG_PATH` to the list in `audit_keys_cmd`, as the issue proposes.
  - Rejected: The audit then still keeps a copy of the rule of the load. The copy became wrong once, when the load got the project layer, and it can become wrong again. The function costs the same lines and removes the copy.

### 2. The audit keeps its scan of the current directory
- Decision: The audit also scans `config.yaml` and `.devops/config.yaml` in the current directory, as before.
- Rationale: These files can hold a plaintext secret also when the settings do not load them, for example when `DEVOPS_CLI_CONFIG` names a different file. Issue #2426 asks the audit to scan more files, not fewer.
- Alternative considered: Scan only the files of `config_layer_paths()`.
  - Rejected: A secret in `./config.yaml` then passes the audit when `DEVOPS_CLI_CONFIG` names a different file. That is a new gap, and no issue asks for it.

### 3. The audit no longer calls `get_active_config_path()`
- Decision: The audit reads the project file that the load reads (`_find_project_config_path()`), not the save target of `get_active_config_path()`.
- Rationale: The two functions give the same file, except in three cases:
  - When `DEVOPS_CLI_CONFIG` names a directory, the load ignores it and walks the tree. The audit now does the same.
  - When `DEVOPS_CLI_CONFIG` holds a `..` segment, also a percent-encoded one, `get_active_config_path()` raises `SecurityError` (`validate_no_path_traversal`).
  - When `DEVOPS_CLI_CONFIG` names a forbidden system path, `get_active_config_path()` also raises `SecurityError`.
- The checks of the last two cases protect the save target, and they stay there. The load reads that file without these checks. On `origin/main`, the audit stopped with `SecurityError` in these two cases. Now it reads and scans the same file that the settings use. The audit only parses the file, and decision 4 keeps the text of the file out of its output.
- Alternative considered: Scan `get_active_config_path()` and `config_layer_paths()`.
  - Rejected: The two lists hold the same files, so the second call only adds a second rule.

### 4. The audit refuses each error of the YAML loader that the load refuses
- Decision: `_scan_yaml_for_secret_keys` catches `_YAML_LOAD_ERRORS` of the settings load and `OSError`. It logs the file, the type of the error and the position from `_yaml_error_location`, and it reports the file unaudited. The scan of the keys is outside the `try` block.
- Rationale: The scanner caught only `YAMLError`, `OSError` and `ValueError`. For `!!bool <text>`, the safe loader raises `KeyError`, and the message holds the value. The audit then stopped with the value in its output and in the log. This change makes the audit read the global file in more cases, so the audit must not show the text of that file. The load and the audit now use one rule for these errors.
- This decision delivers the item of #2451 for `devops config audit-keys`. The items of #2451 for `write_history` and `round_trip` stay open.
- Alternative considered: Call `_read_config_file` and catch `ConfigurationError`.
  - Rejected: Its message starts with "Cannot load the settings". That is false for a file that only the audit reads, such as `./config.yaml`.

### 5. A leak names the full path of its file
- Decision: A leak is `<path>:<section>.<key>`. The path is the resolved path that `scanned_config_files` also shows.
- Rationale: The global file and a project file can both have the name `config.yaml`. The table output does not show `scanned_config_files`. Thus a leak with only the file name does not tell which file holds the secret.
- Alternative considered: Print `scanned_config_files` in the table output.
  - Rejected: The person must then open each file to find the leak.

## Risks / Trade-offs

- [A user with a plaintext secret in the global file now sees exit 1] -> That is the purpose of the audit. The alert names the full path of the file. When that file is not the active file, no `devops config` command removes the value, so the person edits the file. #2513 asks for a command that does this.
- [A leak shows the path of the home directory] -> `scanned_config_files` and the line of an unaudited file show these paths already.
- [A tool that reads `plaintext_leaks` expects `<file name>:<section>.<key>`] -> In devops-cli, only the audit reads this text. Before `1.0.0`, the project keeps no backward compatibility.
