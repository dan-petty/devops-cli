# Tasks

## 1. Behavior & Tests

- [x] 1.1 Write failing tests for `.gitattributes` `linguist-generated=true` coverage, missing-glob detection, `is_secret_scan_only` reading `CONST_DOCS_INVENTORY`, empty generated globs in `CONST_REVIEW_ROUTED_PATH_PATTERNS`, and the `CONTRIBUTING.md` conflict step
  - Verification: `$ uv run pytest -n 0 tests/docs/test_docs_inventory.py tests/review/test_review_diff.py`
- [x] 1.2 Update `.gitattributes`, `src/devops_cli/config/constants.py`, `src/devops_cli/docs/inventory.py`, `src/devops_cli/review/targets.py`, and `CONTRIBUTING.md`
  - Verification: `$ uv run pytest -n 0 tests/docs/test_docs_inventory.py tests/review/test_review_diff.py tests/commands/test_openspec_scaffold.py tests/config/test_tuicr_config.py`

## 2. Documents & CI Gate

- [x] 2.1 Verify `uv run devops docs check`, `uv run devops openspec check`, and `uv run devops ci --check`
  - Verification: `$ uv run devops docs check && uv run devops openspec check && uv run devops ci --check`
