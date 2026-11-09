# Design

## Context

See proposal.md for the scope (#4259, next wave of group 4 of #3769). This change eliminates internal `devops_cli` patches from 8 command test files.

## Decisions

### 1. Replace internal subprocess patches with stdlib / process edge fakes
- **Decision**: In `tests/commands/test_k8s_dry_run.py` and `tests/commands/test_k8s_manifest_dry_run.py`, remove `monkeypatch.setattr("devops_cli.core.process.run_subprocess", ...)`. Keep the stdlib `subprocess.run` and `subprocess.Popen` guards.
- **Why**: `run_subprocess` delegates directly to `subprocess.run`. The stdlib patch already catches unintended executions without patching an internal `devops_cli` name.

### 2. Verify dry-run filesystem state without patching internal writer functions
- **Decision**: In `tests/commands/test_devcontainer_install_tools_dry_run.py` and `tests/commands/test_config_workspace_docs_dry_run.py`, remove patches of `write_text_file`, `write_json_file`, and `save_settings`. Assert on the filesystem and config file state directly.
- **Why**: The behavior under test is that `--dry-run` leaves the disk unchanged. Direct filesystem assertions prove this without inspecting or replacing internal helper functions.

### 3. Replace workspace `_PROJECT_ROOT` patches with configured `repos.base_dir`
- **Decision**: In `tests/commands/test_config_workspace_docs_dry_run.py`, remove patches of `devops_cli.commands.workspace._PROJECT_ROOT`. Configure `repos.base_dir = tmp_path` so paths under `tmp_path` are recognized as valid repository paths.
- **Why**: `_resolve_from_project_root` accepts paths relative to either `_PROJECT_ROOT` or `repos.base_dir`. Configuring `repos.base_dir` uses the standard configuration system instead of patching a module attribute.

### 4. Replace Argo and review internal patches with edge doubles
- **Decision**: In `test_argo.py`, patch `kubernetes.client.CustomObjectsApi` directly at the SDK edge if needed, or use the `cluster` fake. In review tests, use the shared review test fixtures and edge fakes instead of private helpers.
- **Why**: docs/TESTING.md permits patching SDK objects at their own module as a fallback when no seam exists, and bans patching `devops_cli` names.

### 5. RAG ingest command tests use edge doubles
- **Decision**: In `test_rag.py`, replace internal patches of `run_ingest_pass` with mock runner injection or edge fakes (FakeQdrantClient and git repo state under `tmp_path`).
- **Why**: The command connects user input to the ingest engine. Testing through public interfaces ensures full wiring coverage.
