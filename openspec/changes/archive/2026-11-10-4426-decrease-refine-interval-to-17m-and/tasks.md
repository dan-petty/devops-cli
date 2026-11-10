# Tasks

## 1. Defaults and Implementation

- [x] 1.1 Update `DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES` to 17 and `DEFAULT_ROADMAP_REFINE_LIMIT` to 7 in `src/devops_cli/config/defaults.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py`
- [x] 1.2 Update help strings and docstrings in `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/run.py`, and `src/devops_cli/roadmap/refine/refine.py`
  - Verification: `$ uv run devops docs check`

## 2. Test Updates

- [x] 2.1 Update limit classification in `tests/roadmap/test_roadmap_limit_classes.py` and interval table in `tests/roadmap/test_roadmap_run_due_table.py`
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_run_due_table.py tests/roadmap/test_roadmap_limit_classes.py`
- [x] 2.2 Update `refine_round` helper and refine selection tests in `tests/support/roadmap_refine.py` and `tests/roadmap/refine/`
  - Verification: `$ uv run pytest tests/roadmap/refine/`
- [x] 2.3 Update MCP tool listing snapshot in `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`
  - Verification: `$ uv run pytest tests/ai/mcp/test_mcp_tool_listing.py`

## 3. Documents and Quality Gates

- [x] 3.1 Regenerate reference documents with `uv run devops docs generate`
  - Verification: `$ uv run devops docs check`
- [x] 3.2 Run quality gate checks
  - Verification: `$ uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
- [x] 3.3 Archive OpenSpec change
  - Verification: `$ PATH="/home/vscode/.local/bin:$PATH" uv run devops openspec archive 4426-decrease-refine-interval-to-17m-and`
