# Design

## Context

See proposal.md for the background. `load_settings` merges the global config file and the project config file (`_read_config_layers`). `audit_keys_cmd` scans `get_active_config_path()`, which is one of these two files, and `config.yaml` and `.devops/config.yaml` in the current directory. When a project file exists, the audit does not scan the global file.

## Goals / Non-Goals

**Goals:**
- Make the audit scan each config file that the settings merge.
- Give the load and the audit one rule for these files, so that they cannot become different again.

**Non-Goals:**
- Change how the audit finds a plaintext secret, or the text of a leak (`<file name>:<section>.<key>`).
- Change the file that a settings save writes (`get_active_config_path()`).
- Change the error of a config file that is not valid YAML (#1468, `_read_config_file`).

## Decisions

### 1. One public function gives the files that the settings merge
- Decision: `config_layer_paths()` in `src/devops_cli/config/settings.py` gives the global file and the project file (or `None`), in the merge order. `_merged_config_data` gets its files from this function and gives them to `_read_config_layers`. `audit_keys_cmd` scans each file of the function that is not `None`.
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
- Rationale: The two functions give the same file, except in two cases. When `DEVOPS_CLI_CONFIG` names a directory, the load ignores it and walks the tree, and the audit now does the same. When `DEVOPS_CLI_CONFIG` names a forbidden system path, `get_active_config_path()` raises `SecurityError`. That check protects the save target, and it stays there. The load reads that file without the check, so the audit reads the same file that the settings use. The audit only parses the file and logs the error type and position, never its text.
- Alternative considered: Scan `get_active_config_path()` and `config_layer_paths()`.
  - Rejected: The two lists hold the same files, so the second call only adds a second rule.

## Risks / Trade-offs

- [The global file and the project file both have the name `config.yaml`] -> A leak names the file name only, so `config.yaml:ai.api_key` does not tell which file holds it. `scanned_config_files` names the full path of each file. The text of a leak does not change in this change.
- [A user with a plaintext secret in the global file now sees exit 1] -> That is the purpose of the audit. The report names the leak and the command that moves the secret to the keyring.
