# Task #857: MCP ToolAnnotations (`readOnlyHint`) and Safe `tf_apply` Default

**Issue**: [#857](https://github.com/dan-petty/devops-cli/issues/857)
**Feasibility**: Confirmed against FastMCP 3.4.7 (`mcp._list_tools()`) and MCP SDK v2 (`ToolAnnotations`): passing `annotations={"readOnlyHint": True/False}` to `@mcp.tool(...)` populates `tool.annotations.read_only_hint` on all 155 registered tools and serializes to `{"readOnlyHint": true/false}` via `model_dump(by_alias=True, exclude_none=True)`.

## Deliverables

- [x] Annotated all 155 tools registered in `src/devops_cli/ai/mcp/server.py` with `annotations={"readOnlyHint": True}` or `annotations={"readOnlyHint": False}`, classifying argument-dependent mutating tools (`roadmap_render`, `gh_project_reconcile`, `docker_sign`, `argo_rollout_analyze`, `rag_drift`, `review_pr`, `gh_label_sync`, etc.) for their most dangerous arguments (`readOnlyHint: False`).
- [x] Added `CONST_MCP_ARGUMENT_MUTATING_TOOLS_FLOOR` in `src/devops_cli/config/constants.py` and `test_fastmcp_tool_annotations_and_mutating_floor` in `tests/test_fastmcp_contracts.py` verifying every registered tool sets `readOnlyHint` and holding the argument-mutating tool floor.
- [x] Changed `tf_apply` in `src/devops_cli/ai/mcp/server.py` to default to `auto_approve: bool = False` and verified via `TestTfMcpTools.test_tf_apply_tool` in `tests/test_mcp.py`.
- [x] Carried `read_only_hint` (`readOnlyHint`) into `MCPToolInfo` (`src/devops_cli/models/ai.py`), `devops mcp export-schemas` (`src/devops_cli/commands/mcp.py`), `MCPToolDoc` (`src/devops_cli/docs/generator.py`), and regenerated `docs/MCP_TOOLS.md`.
