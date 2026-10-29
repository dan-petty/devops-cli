# Proposal

## Why

Issue #2513: `devops config audit-keys` finds a plaintext secret in each config file that the settings merge (#2426), but its alert names no command that removes the secret. The alert says to run `devops config set <key> <val>`. That command stores a credential in the OS keyring and writes no config file, so the plaintext value stays and the audit fails again. The alert also puts the secret in the argument list, although `devops config set <key>` asks for a credential at a hidden prompt.

A plain `devops config unset <key>` edits only the active config file. When the leak is in another file, the command exits 1 with "The config file <file> does not hold the key". The usual case is the global file `~/.config/devops-cli/config.yaml` while a project file is active, as in the devcontainer. The person then edits the file by hand.

## What Changes

- The alert of `devops config audit-keys` names two commands. `devops config set <key>` stores a credential in the keyring. `DEVOPS_CLI_CONFIG=<file> devops config unset <key>` removes the plaintext value from the file of the leak. The alert also says that each leak reads `<file>:<key>`, and that a key that is not a config option needs only the second command.
- The alert text moves to `ConfigMessages.plaintext_alert` in `src/devops_cli/lang/en/messages.py`.
- The help of `devops config audit-keys` names the same command as the alert. The help of `devops config unset` says that `DEVOPS_CLI_CONFIG` names the file that the command edits. `devops docs generate --sync-readme` writes both texts into the generated documents, and `docs/CONFIGURATION.md` and the knowledge base name the command.
- `tests/test_config_audit_keys.py` follows the alert: it runs the named command for a leak in the global file and for a leak in `config.yaml` of the current directory, and it checks that the next audit passes.
- No command or option is added. The alert, the help and the message of a leak are observable, so the change has a spec delta for the `config-commands` capability.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: adds the requirement that the alert and the help of `devops config audit-keys` name a command that removes a leak from the file that holds it.

## Impact

- `src/devops_cli/commands/config.py`: `audit_keys_cmd` prints `MESSAGES.config.plaintext_alert`. The docstrings of `audit_keys_cmd` and `unset_value` name the command.
- `src/devops_cli/lang/en/messages.py`: the message `plaintext_alert`.
- `src/devops_cli/docs/generator.py`, `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md`: the text of the command.
- `tests/test_config_audit_keys.py`: two tests, and the fixture of the global file removes the copies that a write of it makes.
- Generated documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/CONFIGURATION.md`, `docs/MCP_TOOLS.md`, `docs/commands/config.md`.

## Feasibility

- Confirmed with command output on devops-cli 0.16.0 at `origin/main` 7dde54e8, with a temporary `HOME` and `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring`. The global file held `ai:` and `  api_key: FAKE-2513-value`. The file `.devcontainer/config.yaml` of a git repository held `log_level: INFO`. `DEVOPS_CLI_CONFIG` was not set.
- `devops config audit-keys` exited 1 and named the global file. Its alert named `devops config set <key> <val>` only. `devops config unset ai.api_key` exited 1 with "The config file <repo>/.devcontainer/config.yaml does not hold the key 'ai.api_key'. Nothing changed." `devops config set ai.api_key <value>` printed "stored in keyring" and left the global file as it was.
- One command already removes the value. `DEVOPS_CLI_CONFIG=<global file> devops config unset ai.api_key` removed the key from the global file, and the next audit exited 0. `get_active_config_path()` returns the file that `DEVOPS_CLI_CONFIG` names, so `unset` edits that file. The error of an unknown key already names this command for a key in another file (`unknown_keys.py`). Thus the premise "no command removes the secret" holds only in part: the command exists, but no text names it for a leak. The defect stays in a narrower form, and this change fixes it at its source, which is the text of the alert and the help.
- The new test `test_config_audit_keys_alert_names_a_command_that_removes_the_leak_from_its_file` fails on `origin/main` in both cases, at the check of the alert text.

## Existing Tool Considered

The need is a way to remove a key from a named config file. The command `devops config unset` and the variable `DEVOPS_CLI_CONFIG` already do this, and the error of an unknown key already uses them. Thus the change builds no new option and no new code path, and it only names the existing command in the alert, the help and the documents. No open tool knows which files the settings of devops-cli merge. The change deletes the old alert text, which named a command that does not remove the plaintext value.
