# Tasks

## 1. Constants and limits

- [x] 1.1 Define consolidate budget, request timeout, margin, and maximum limit constants in `src/devops_cli/config/constants.py`
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_consolidate_judge.py`
- [x] 1.2 Add `max=20` to the `--limit` option in `src/devops_cli/commands/roadmap.py` and verify published MCP schema
  - Verification: `$ uv run pytest tests/ai/mcp/test_mcp_tool_schemas.py`

## 2. Consolidate run budget and judge timeouts

- [x] 2.1 Implement deadline and remaining budget checks in `src/devops_cli/roadmap/consolidate.py` and `src/devops_cli/roadmap/consolidate_judge.py`
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_consolidate_judge.py`
- [x] 2.2 Handle request timeouts and short budget by marking shortlists unjudged without aborting the run
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_consolidate.py`
- [x] 2.3 Print diagnostic to stderr when run budget ends with unjudged shortlists and exit 0
  - Verification: `$ uv run pytest tests/commands/test_roadmap_consolidate_cmd.py`

## 3. Timeout chain and quality gates

- [x] 3.1 Add offline nested limit chain test
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_consolidate_timeouts.py`
- [x] 3.2 Run quality gates and pre-commit checks
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor,lint,test-tree,constructs,swallowed-failures,typecheck,startup-imports`
