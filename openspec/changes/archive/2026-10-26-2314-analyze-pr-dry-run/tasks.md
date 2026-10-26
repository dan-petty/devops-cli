# Tasks

## 1. Dry run of analyze pr

- [x] Add a failing test for `analyze pr` under `--dry-run` and the dry-run environment
  - Verification: `uv run devops ci test tests/test_analyze.py -k dry_run_previews`
- [x] Render the preview before the GitHub session and remove the dead dry-run branches
  - Verification: `uv run devops ci test tests/test_analyze.py`
- [x] Regenerate documentation
  - Verification: `uv run devops docs generate --sync-readme`
- [x] Archive the change
  - Verification: `uv run devops openspec archive 2314-analyze-pr-dry-run`
