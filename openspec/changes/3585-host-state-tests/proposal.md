# Proposal

## Why

Issue #3585: four tests and one contract case of `uv run devops ci` read the state of the host, so the gate fails on a devcontainer that the tests do not own. A stray `/tmp/config.yaml` fails two tests. The devcontainer CLI in the default tool directory fails the install-tools status test (the same test as in #3025). A Popeye binary in the tool directory of the user fails the direct-executor case and its teardown.

The cause of the two config failures is in product code: the project config search, and a copy of it in the SSH key prefix search, walk up to the root of the file system. They accept a `config.yaml` in any ancestor, such as a shared `/tmp`.

## What Changes

- `project_config_directories` in `config/settings.py` gives the one walk: the base directory, then each ancestor up to and including the first project root (`.git` or `.devcontainer`), and an ancestor counts only when it is a project root.
- `_find_project_config_path` and the SSH key prefix search use that walk. This removes the second copy of the walk in `crypto/ssh_keys.py`.
- `test_mark_only_commands_under_global_dry_run` gives `install-tools status` an empty target directory and an empty PATH. A new test shows `at pin` for the devcontainer CLI when it is at its pin, and `not installed` when it is not (#3025).
- The direct-executor network-profile case puts a Popeye stand-in first on PATH and asserts that it never starts.
- New tests for the project root rule in `tests/telemetry/test_config_env_overrides.py` and `tests/crypto/test_ssh.py`.
- The change alters a behavior that a user observes (which config file counts), so it carries a spec delta.
- This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `config-commands`: adds the project root rule of the config search.

## Impact

- `src/devops_cli/config/settings.py`, `src/devops_cli/crypto/ssh_keys.py`.
- `tests/telemetry/test_config_env_overrides.py`, `tests/crypto/test_ssh.py`, `tests/commands/test_devcontainer_install_tools_dry_run.py`, `tests/ai/test_tool_executor_contract.py`.

## Feasibility

Checked on this host with the four modules (`uv run devops ci test`):
- With a stray `/tmp/config.yaml` that sets `ssh.key_prefix`, `test_get_ssh_key_prefix_resolution` and `test_find_project_config_path_skips_directory` fail. The SSH test fails through `_resolve_prefix_from_project_config`, which walks the ancestors of the workspace. It does not read the process working directory, so the design step "change into the directory under test" cannot fix it: the walk starts from the given directory. The fix is the project root rule.
- `install-tools status` reads the target directory first (default `~/.local/bin`), and PATH second. A test that sets PATH only still shows the tool of the default target directory. So the test gives `--target-dir` too. `installed_commands` reads the user data root, which the test floor already puts under `tmp_path`.
- `resolve_tool_binary` finds `popeye` with `shutil.which`, so a stand-in first on PATH is resolved in place of the host tool.

## Existing Tool Considered

pytest `monkeypatch` and `tmp_path` cover the test side, and the project already uses them. No library covers the project root rule: it is four lines in one function that is shared by two callers. Cost: about 40,000 tokens and one hour, and it deletes the second copy of the walk in `crypto/ssh_keys.py`.
