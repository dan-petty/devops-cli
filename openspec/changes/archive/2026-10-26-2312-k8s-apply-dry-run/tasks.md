# Tasks

## 1. Dry run of k8s apply

- [x] Add a failing test for `k8s apply` under `--dry-run`, the `--template` path and the dry-run environment
  - Verification: `uv run devops ci test tests/test_k8s_context.py -k dry_run`
- [x] Gate `apply` and `_apply_template` on `dry_run or is_dry_run()` before the subprocess runner
  - Verification: `uv run devops ci test tests/test_k8s_context.py`
- [x] Regenerate documentation
  - Verification: `uv run devops docs generate --sync-readme`
- [x] Archive the change
  - Verification: `uv run devops openspec archive 2312-k8s-apply-dry-run`
