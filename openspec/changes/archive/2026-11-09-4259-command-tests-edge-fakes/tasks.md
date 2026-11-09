# Tasks

## 1. Dry run command tests reach edge fakes (test-only edits)

- [x] 1.1 Remove `run_subprocess` monkeypatch from `tests/commands/test_k8s_dry_run.py` and `tests/commands/test_k8s_manifest_dry_run.py`.
  Verification: `uv run pytest tests/commands/test_k8s_dry_run.py tests/commands/test_k8s_manifest_dry_run.py`
- [x] 1.2 Remove `write_text_file` and `write_json_file` patches from `tests/commands/test_devcontainer_install_tools_dry_run.py`.
  Verification: `uv run pytest tests/commands/test_devcontainer_install_tools_dry_run.py`
- [x] 1.3 Remove `save_settings` and `_PROJECT_ROOT` patches from `tests/commands/test_config_workspace_docs_dry_run.py`.
  Verification: `uv run pytest tests/commands/test_config_workspace_docs_dry_run.py`

## 2. Argo, RAG and Review command tests reach edge fakes (test-only edits)

- [x] 2.1 Replace internal `ArgoCRDService._api` and `LiveResourceWatcher.watch` patches in `tests/commands/test_argo.py` with SDK-level or cluster fakes.
  Verification: `uv run pytest tests/commands/test_argo.py`
- [x] 2.2 Replace `run_ingest_pass` patches in `tests/commands/test_rag.py` with edge fakes or public runner parameters.
  Verification: `uv run pytest tests/commands/test_rag.py`
- [x] 2.3 Replace private review helper patches in `tests/commands/test_review_scope.py` and `tests/commands/test_review_adjudication.py` with edge doubles.
  Verification: `uv run pytest tests/commands/test_review_scope.py tests/commands/test_review_adjudication.py`

## 3. Verify no devops_cli name patches remain in target files

- [x] 3.1 Check that none of the 8 target files holds a patch of a `devops_cli` name.
  Verification: `! git grep -n -E "(monkeypatch\.setattr|patch(\.object)?)\(.*['\"]devops_cli" tests/commands/test_argo.py tests/commands/test_devcontainer_install_tools_dry_run.py tests/commands/test_k8s_dry_run.py tests/commands/test_k8s_manifest_dry_run.py tests/commands/test_rag.py tests/commands/test_config_workspace_docs_dry_run.py tests/commands/test_review_scope.py tests/commands/test_review_adjudication.py`

## 4. Documents and gate

- [x] 4.1 Validate OpenSpec change folder.
  Verification: `uv run devops openspec check`
- [x] 4.2 Run fast checks.
  Verification: `uv run devops ci --check --only lint,format`
- [x] 4.3 Archive OpenSpec change.
  Verification: `uv run devops openspec archive 4259-command-tests-edge-fakes`
