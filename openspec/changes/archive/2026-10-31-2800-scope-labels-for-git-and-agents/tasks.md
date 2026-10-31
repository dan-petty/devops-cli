## 1. The contract of the title check

- [x] 1.1 Write the failing test `test_the_title_check_allows_exactly_the_declared_scopes` in `tests/invariants/test_workflow_contracts.py`. Verify: `uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 1.2 Declare the 15 scopes in `.github/labels.yml`. Verify: `uv run devops ci test tests/invariants/test_workflow_contracts.py tests/commands/test_pr_title_labels.py`
- [x] 1.3 Set `scopes` in `.github/workflows/pr-title.yml`. Verify: `uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 1.4 Say in `CONTRIBUTING.md` that the scope of a title is a declared scope, and run `uv run devops docs generate --sync-readme`.

## 2. Verification

- [x] 2.1 Run `uv run devops ci fail-to-pass --base origin/main`.
- [x] 2.2 Run the full `uv run devops ci` once.
- [x] 2.3 Archive the change with `uv run devops openspec archive 2800-scope-labels-for-git-and-agents`.
