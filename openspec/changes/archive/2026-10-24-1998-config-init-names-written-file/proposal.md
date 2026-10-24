# Proposal

## Why

Issue #1998: `devops config init` showed `CONST_CONFIG_PATH` as the file that it wrote, but `save_settings` wrote the active config path. When the active path is a different file, for example the file that `DEVOPS_CLI_CONFIG` names or a project config, the message named the wrong file. The user then looked for the new values in a file that did not get them.

## What Changes

- `devops config init` resolves the active config path one time, gives that path to `save_settings`, and shows the same path in its `Config file:` line. Thus the message always names the file that the wizard wrote.
- The `CONST_CONFIG_PATH` import of `src/devops_cli/commands/config.py` goes, because no code in the module uses it now.
- The `Config file:` line is output of a `devops` command, which a user can see, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `config-commands`: what the `devops config` commands tell the user about the config file that they write.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/commands/config.py` (the `init` command).
- Tests: `tests/commands/test_config.py` (new).
- `src/devops_cli/config/settings.py` does not change: `save_settings` already takes the destination path as `target_path`.

## Feasibility

- In `src/devops_cli/commands/config.py` on the base commit, `init` called `save_settings(settings)` with no `target_path`, and then showed `CONST_CONFIG_PATH`. In `src/devops_cli/config/settings.py`, `save_settings` writes to `target_path or get_active_config_path()`, and `get_active_config_path` returns the `DEVOPS_CLI_CONFIG` file, then a project config, and only then `CONST_CONFIG_PATH`.
- `devops config show` already shows `get_active_config_path()`, so `init` was the only `config` command that named the default path.
- On the base commit, `uv run devops ci test tests/commands/test_config.py` failed. The test floor sets `DEVOPS_CLI_CONFIG` to a file under `tmp_path`. The wizard wrote the new default org to that file, but its output was `Config file: <tmp>/home/.config/devops-cli/config.yaml`, which is `CONST_CONFIG_PATH` under the isolated home directory.

## Existing Tool Considered

No tool is necessary. The change uses the `target_path` parameter that `save_settings` already has, and `get_active_config_path`, which `devops config show` already uses. Nothing is built. The change deletes the `CONST_CONFIG_PATH` import of `src/devops_cli/commands/config.py`.
