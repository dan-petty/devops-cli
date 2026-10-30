# Proposal

## Why

Issue #2645: `devops config unset <key>` copies the config file to `<name>.bak-<YYYYMMDD-HHMMSS>` before it removes the key. When the key is a plaintext credential, the copy holds the credential. The copy has the mode of the file, and the command keeps the newest 10 copies. Thus the removal of a credential leaves the credential on disk, and `devops config audit-keys` does not scan the copies, so it reports no leak.

The copies that earlier writes made hold the credential too. A write of any other key, such as `devops config set ai.model <value>`, copies the whole file first. So a copy that only the new copy redacts would still leave the credential in up to 9 older copies.

Issue #2513 made the alert of `devops config audit-keys` say that the copy still holds the value and that a person deletes it by hand. That sentence is a workaround for this defect. This change removes it.

## What Changes

- `devops config unset <key>` shows the value of each credential that it removes as `***REDACTED***` in the new copy and in each retained older copy. The key stays, so a person sees that a value was there. Every other line of the copy stays as it was, so a person can still undo the removal of another key.
- A key counts as a credential when its dotted name is in the set of credentials of `devops_cli.config.env` (`secret_keys()`). A removal of a section, such as `ai`, redacts each credential below it.
- A copy that holds no value to redact (an empty value, the placeholder, or no such key) stays byte for byte as it is. A copy that is not UTF-8 text, is not YAML, or is not a YAML mapping stops the command with a `ConfigurationError` that names the copy and quotes no text. The command stops before it replaces the file, so no credential is removed and left in that copy.
- A comment line of a copy that holds the value, such as `# was <value>`, loses its comment text. The copies keep their line ends (CRLF stays CRLF).
- The copy keeps the mode of the file. The retention of 10 copies does not change. A write that is not a removal does not redact: its copy only repeats the file as it was.
- The alert of `devops config audit-keys` no longer says that the copy still holds the value. The requirement that said so is renamed and changed.
- The help of `devops config unset`, the generated documents and the knowledge base say what the copies show.
- This change fits in one pull request. It changes an observable command and message, so it has a spec delta for the `config-commands` capability.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: the copy of `devops config unset` holds no credential value, and the alert of `devops config audit-keys` no longer warns about a copy.

## Impact

- `src/devops_cli/config/write_history.py`: `back_up` takes the key paths to redact. New helpers `credential_paths`, `_copy` and `_redact`.
- `src/devops_cli/config/settings.py`: `remove_config_key` passes the credentials of the removed key to `_write_content`, which passes them to `back_up`.
- `src/devops_cli/config/constants.py`: `CONST_CONFIG_REDACTED_VALUE`.
- `src/devops_cli/lang/en/messages.py`: the alert loses the sentence about the copy.
- `src/devops_cli/commands/config.py`, `src/devops_cli/docs/generator.py`, `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md`: the help and the documents.
- `tests/config/test_config_key_removal.py`, `tests/commands/test_config.py`, `tests/test_config_audit_keys.py`.
- Generated documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/CONFIGURATION.md`, `docs/MCP_TOOLS.md`, `docs/commands/config.md`.

## Feasibility

- Confirmed with command output at `origin/main` a3453463 (devops-cli 0.21.2). A temporary `HOME` held `ai.api_key` with the fake value `FAKE-2513-value` in the global config file. `DEVOPS_CLI_CONFIG` was not set, the keyring was `keyring.backends.null.Keyring`, and the working directory held no project file. `devops config unset ai.api_key` exited 0 and named the copy. `cat` of the copy printed `api_key: FAKE-2513-value`. The copy had the mode 0644, as the file did. The defect exists on `main`.
- The code confirms the cause. `_write_content` in `src/devops_cli/config/settings.py` calls `back_up` in `src/devops_cli/config/write_history.py`, and `back_up` calls `shutil.copy2`, a byte copy.
- The credential keys come from `secret_keys()` in `src/devops_cli/config/env.py`, the set that `dotted_set` and the audit already use.
- The first design of the issue redacts the new copy only. A probe of the code shows that each write of another key makes a copy of the whole file, and `back_up` keeps 10. So the redaction also covers the retained older copies. The test `test_a_removal_of_a_credential_redacts_it_in_each_copy_that_an_earlier_write_made` fails on `origin/main` and passes after the change.
- The new tests fail on `origin/main` (`uv run devops ci fail-to-pass --base origin/main`).

## Existing Tool Considered

`ruamel.yaml`, which `devops_cli.config.round_trip` already wraps, reads and edits a YAML text and keeps its comments and layout. The change uses `round_trip.edit` and `round_trip.leaves` to set the values, and it builds no YAML code. No open tool redacts the keys of a YAML file by their dotted names against the credential set of devops-cli. Cost of the new code: about 60 lines in `write_history.py` and 5 lines in `settings.py`, and about 150 lines of tests. The elapsed time to build was about one hour, and the maintenance is one function and its caller.

The change deletes the sentence of the alert that told a person to delete the copy by hand.
