# Proposal: #4266

## Why

Issue #3769 asks that no command test patches a name inside `devops_cli`. It splits the work by command group. Groups 1 to 3 and the first waves of group 4 are merged (#4105, #4097, #4103, #4100, #4259).

This item continues group 4 of #3769. It targets 6 command test files:
- `tests/commands/test_config_commands.py`
- `tests/commands/test_workspace.py`
- `tests/commands/test_devcontainer.py`
- `tests/commands/test_tf.py`
- `tests/commands/test_test_runner.py`
- `tests/commands/test_k8s_bootstrap_mattermost.py`

These files hold 95 string patches of a `devops_cli` name. The patches double code inside the process instead of the edges that the commands reach. Issue #1336 turns the ratchets into bans and fails on these patches. Closes #4266.

## What Changes

- In `tests/commands/test_config_commands.py`, replace internal patches of `load_settings`, `save_settings`, `dotted_set`, `_validate_wizard_service_url`, `check_binary`, and `stream_audit_records` with `config`, `isolate_devops_cli_config`, and edge doubles.
- In `tests/commands/test_workspace.py`, replace `_PROJECT_ROOT`, `load_settings`, `run_subprocess`, `cleanup_data_tier`, and `DEFAULT_MAX_AST_FILE_SIZE_BYTES` patches with real directory fixtures (`tmp_path`), `process_fake`, and standard configuration.
- In `tests/commands/test_devcontainer.py`, replace 20 `run_subprocess` monkeypatches, 2 `get_engine` patches, and 1 `_start_session_bus` patch with `process_fake` and docker engine edge doubles.
- In `tests/commands/test_tf.py`, replace `is_dry_run`, `_resolve_tf_binary`, `find_worktree_root`, `_get_cloud_dir`, and `run_tflint_scan` patches with CLI `--dry-run` invocation, `process_fake`, and real filesystem paths.
- In `tests/commands/test_test_runner.py`, replace `run_subprocess`, `shutil.which`, `WorkloadSandboxRunner`, `print_info`, and `print_success` patches with `process_fake`, stdlib `shutil.which` patches, and process doubles.
- In `tests/commands/test_k8s_bootstrap_mattermost.py`, replace `_run_cmd`, `store_keyring_secret`, `push_secrets`, and `run_subprocess` patches with `process_fake`, `cluster` fake, and `keyring` edge doubles.

## Capabilities

- Command tests execute against hermetic edge doubles (process, cluster, keyring, filesystem) without monkeypatching internal devops-cli symbols.
- Test suites run identically under CI without artificial test switches or state pollution.

## Impact

- Zero functional impact on product code behavior.
- Command test suites become more robust and refactor-safe.
- Unblocks issue #3769 completion and subsequent ratchet-to-ban conversion under #1336.

## Feasibility

Verified by `git grep -n -E "(monkeypatch\.setattr|patch(\.object)?)\(.*['\"]devops_cli" tests/commands/` finding exactly 95 patch sites across the 6 named files. The existing shared edge fakes (`tests/support/fakes/process.py`, `kubernetes.py`, `keyring.py`) and config fixtures already provide all required capabilities.

## Existing Tool Considered

No new tool is needed. `pytest` with the edge fakes of `tests/support/fakes/` (process, cluster, keyring), the `config` fixture, `tmp_path`, and the `cli` fixture cover the need.
