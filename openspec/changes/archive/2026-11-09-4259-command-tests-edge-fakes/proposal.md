# Proposal

## Why

Issue #4259 is the next wave of group 4 of #3769. #3769 requires that command tests patch no name inside `devops_cli`. Groups 1 to 3 and the first wave of group 4 migrated 54 files to edge fakes (#4105, #4097, #4103, #4100).

The target files hold 21 string patches of a `devops_cli` name across 8 files:
- `tests/commands/test_argo.py` (2)
- `tests/commands/test_devcontainer_install_tools_dry_run.py` (2)
- `tests/commands/test_k8s_dry_run.py` (1)
- `tests/commands/test_k8s_manifest_dry_run.py` (1)
- `tests/commands/test_rag.py` (3)
- `tests/commands/test_config_workspace_docs_dry_run.py` (4)
- `tests/commands/test_review_scope.py` (3)
- `tests/commands/test_review_adjudication.py` (5)

These patches double functions inside the process: `run_subprocess`, `write_text_file`, `write_json_file`, `save_settings`, `commands.workspace._PROJECT_ROOT`, `run_ingest_pass`, `ArgoCRDService._api`, and review workflow helpers. Each internal double hides the edge that the command reaches. Issue #1336 turns ratchets into bans and fails on these patches.

## What Changes

This change migrates the 8 command test files to shared edge fakes:
- `tests/commands/test_argo.py`: Replace `ArgoCRDService._api` and `LiveResourceWatcher.watch` internal patches with the `cluster` fixture or SDK doubles at `kubernetes.client`.
- `tests/commands/test_devcontainer_install_tools_dry_run.py`: Remove `write_text_file` and `write_json_file` patches; verify dry-run non-modification directly against the file system.
- `tests/commands/test_k8s_dry_run.py` and `tests/commands/test_k8s_manifest_dry_run.py`: Drop the internal `run_subprocess` monkeypatch; rely on `subprocess.run` faking and `process_fake`.
- `tests/commands/test_rag.py`: Use edge fakes for Qdrant and git repository state instead of monkeypatching `run_ingest_pass`.
- `tests/commands/test_config_workspace_docs_dry_run.py`: Remove the `save_settings` patch; verify config immutability via `isolate_devops_cli_config`. Use real repository root resolution with `repos.base_dir` configured instead of patching `_PROJECT_ROOT`.
- `tests/commands/test_review_scope.py` and `tests/commands/test_review_adjudication.py`: Replace private `_make_review_clients` and `_prepare_pr_content` patches with edge doubles (model fakes and git/session fakes).
- Each test keeps its node id and the behavior it checks.
- This change touches no production code under `src/` and alters no consumer-observed behavior. `skip_specs: true` is set.
- This change fits one pull request.

## Impact

- `tests/commands/`: The 8 target files hold 0 string patches of a `devops_cli` name after this change.
- The total count of internal string patches in `tests/commands/` drops from 188 to 167.

## Feasibility

- The edge fakes exist in `tests/support/fakes/`: `process_fake`, `cluster`, `web`, `config`, and `keyring_store`.
- `isolate_devops_cli_config` provides isolated configuration files.
- `tests/commands/test_devcontainer_install_tools_dry_run.py` tests already assert that files do not exist or remain unchanged on disk.
- All 8 files pass on existing fixtures and fakes.

## Existing Tool Considered

No new tool is needed. `pytest` with existing edge fakes in `tests/support/fakes/` and fixtures in `tests/support/` covers the requirements.
