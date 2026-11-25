# Tasks

## 1. Remove the tests and repair the tests that stay

Kind: other

- [x] 1.1 Remove the 160 test functions that hold a value of a real file, a default or a constant, with the helpers, the chart fixture and the snapshot that only they used.
  - Verification: `$ uv run devops ci test tests/invariants tests/commands/test_ci.py tests/core tests/config`
- [x] 1.2 Change the 33 tests that check source code so that they compare with the constant, the setting or input of their own, and regenerate the snapshot of `tests/roadmap/implement/test_roadmap_implement_step.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py tests/ai/test_ai_client_style_request.py tests/commands/test_pr_dry_run.py tests/invariants/test_architectural_invariants.py`

## 2. Gate data and documents

Kind: other

- [x] 2.1 Lower the counts of `tests/gate/tree_checks/config_reads.toml`, remove the six `--deselect` lines of `pyproject.toml` and the duration records of the deleted files.
  - Verification: `$ uv run devops ci --check --only test-tree,lint,format,typecheck`
- [x] 2.2 Correct `SECURITY.md`, `docs/TESTING.md`, `k8s/README.md` and the source comments that named a removed test.
  - Verification: `$ uv run devops ci --check --only docs,openspec`

## Workflow follow-up

- The gate checks of `tests/gate/k8s_checks/` that hold a manifest value: #7231.
- The knowledge base pages that state a locked version: #7232.
- The Python minor version in `src/devops_cli/config/defaults.py`: #6410.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
