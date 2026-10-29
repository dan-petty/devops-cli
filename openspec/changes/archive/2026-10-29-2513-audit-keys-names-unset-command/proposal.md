# Proposal

## Why

Issue #2513: `devops config audit-keys` finds a plaintext secret in each config file that the settings merge (#2426). Its alert names no command that removes the secret. The alert says to run `devops config set <key> <val>`. That command stores a credential in the OS keyring and writes no config file. The plaintext value stays, and the audit fails again.

A plain `devops config unset <key>` edits only the active config file. When the leak is in another file, the command exits 1 with "The config file <file> does not hold the key". This is usual for the global file `~/.config/devops-cli/config.yaml` while a project file is active, as in the devcontainer. The person then edits the file by hand.

The old alert also gave the value in the argument list. The prompt of `devops config set <key>` reads one line, so a multi-line credential, such as a PEM key, needs `--from-file`.

## What Changes

- The alert of `devops config audit-keys` gives two steps for each leak. Step 1 is `devops config set <key>`, with `--from-file <path>` for a multi-line credential. Step 2 is `DEVOPS_CLI_CONFIG=<file> devops config unset <key>`, with the file and the key quoted for the shell.
- The alert says that step 2 keeps a copy of the file that still holds the value. It says that a person deletes the copy by hand. The copy itself is #2645.
- The alert text moves to `ConfigMessages.plaintext_alert` in `src/devops_cli/lang/en/messages.py`. The alert and the line of an unaudited file print with `safe=True`. A name such as `[/x]` then does not stop the print with a `MarkupError`.
- The help of `devops config audit-keys` and of `devops config unset`, the generated documents and the knowledge base name the same commands.
- `tests/test_config_audit_keys.py` follows the alert for a leak in the global file and for a leak in `config.yaml` of the current directory. It stores a PEM-shaped credential with `--from-file`, and it checks that the next audit passes.
- No command or option is added. The alert, the help and the messages are observable, so the change has a spec delta for the `config-commands` capability.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: the alert and the help of `devops config audit-keys` name the commands that remove a leak. The alert prints for any name.

## Impact

- `src/devops_cli/commands/config.py`: `audit_keys_cmd` prints `MESSAGES.config.plaintext_alert` with `safe=True`. The docstrings of `audit_keys_cmd` and `unset_value` name the commands.
- `src/devops_cli/lang/en/messages.py`: the message `plaintext_alert`.
- `src/devops_cli/docs/generator.py`, `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md`: the text of the commands.
- `tests/test_config_audit_keys.py`: new tests, and the fixture of the global file removes the copies that a write of it makes.
- Generated documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/CONFIGURATION.md`, `docs/MCP_TOOLS.md`, `docs/commands/config.md`.

## Feasibility

- Confirmed with command output on devops-cli 0.16.0 at `origin/main` 7dde54e8. A temporary `HOME` held `ai.api_key` with the value `FAKE-2513-value` in the global file. The file `.devcontainer/config.yaml` of a git repository held `log_level: INFO`. `DEVOPS_CLI_CONFIG` was not set, and the keyring was `keyring.backends.null.Keyring`.
- `devops config audit-keys` exited 1 and named the global file. Its alert named `devops config set <key> <val>` only. `devops config unset ai.api_key` exited 1 with "The config file <repo>/.devcontainer/config.yaml does not hold the key 'ai.api_key'. Nothing changed." `devops config set` wrote no config file.
- One command already removes the value. `DEVOPS_CLI_CONFIG=<global file> devops config unset ai.api_key` removed the key, and the next audit exited 0. `get_active_config_path()` returns the file that `DEVOPS_CLI_CONFIG` names. The error of an unknown key already names this form (`unknown_keys.py`).
- Thus the premise "no command removes the secret" holds only in part: no text names the command. This change fixes that text at its source.
- The review of the first version found more defects, and a probe confirmed each one. The prompt of `devops config set <key>` read one line and kept only the first line of a PEM key. Text such as `[/x]` in a leak stopped the alert with a `MarkupError`. A section name with shell syntax ran when a person pasted it into the command.
- One case still fails: `devops config unset` ends with a `TypeError` for a key that a YAML merge key gives (#2656).
- The new tests fail on `origin/main`.

## Existing Tool Considered

The need is a way to remove a key from a named config file. The command `devops config unset` and the variable `DEVOPS_CLI_CONFIG` already do this, and the error of an unknown key already uses them. Thus the change builds no new option and no new code path. It names the existing commands in the alert, the help and the documents.

No open tool knows which files the settings of devops-cli merge. The change deletes the old alert text, which named a command that does not remove the plaintext value.
