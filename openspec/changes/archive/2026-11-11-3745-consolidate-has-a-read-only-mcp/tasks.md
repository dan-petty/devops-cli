# Tasks

## 1. Behavior

- [x] 1.1 Write the failing contract test of the tool `roadmap_consolidate`: its options, its read-only flag and its argv
  - Verification: `$ uv run pytest tests/ai/mcp/test_mcp_roadmap_tools.py`
- [x] 1.2 Add the exposure row and the option restriction of the tool
  - Verification: `$ uv run pytest tests/ai/mcp/test_mcp_roadmap_tools.py tests/ai/mcp/test_mcp_exposure_table.py tests/ai/mcp/test_mcp_read_only_write_options.py`
- [x] 1.3 Update the tool listing snapshot and the row census of the stage run allow-list
  - Verification: `$ uv run pytest tests/ai/mcp/test_mcp_tool_listing.py tests/roadmap/stage/test_stage_run_allowlist.py`

## 2. Documents

- [x] 2.1 Name the tool in `docs/roadmap/consolidate.md` and regenerate `docs/MCP_TOOLS.md`
  - Verification: `$ uv run devops docs generate --sync-readme`
