# Task #1498: Strip FastMCP Injected `ctx` Parameter From Agent Tools

**Issue**: [#1498](https://github.com/dan-petty/devops-cli/issues/1498)
**Feasibility**: Confirmed against `src/devops_cli/ai/tools/mcp_bridge.py`, `src/devops_cli/ai/tools/__init__.py`, and `fastmcp.server.dependencies.without_injected_parameters`. FastMCP 4.0.11 rewrites `hydrate_tool_domain(domain: str, ctx: Context | None = None)` in place with `ctx=OptionalCurrentContext()`, causing `Tool.from_function` to emit `PydanticJsonSchemaWarning` and advertise `ctx` in the tool's JSON schema. Wrapping each tool function in `without_injected_parameters` strips injected `Context` and `Depends` parameters from the signature and resolves `ctx` to `None` when called outside an MCP session; resolving awaitables in `Tool.execute` ensures synchronous agent tool execution returns the concrete dictionary result.

## Deliverables

- [x] Wrap each FastMCP tool callable returned by `get_mcp_agent_tools()` in `src/devops_cli/ai/tools/mcp_bridge.py` with `fastmcp.server.dependencies.without_injected_parameters`.
- [x] Resolve awaitable return values in `Tool.execute()` in `src/devops_cli/ai/tools/__init__.py` via `_run_coroutine_sync`.
- [x] Add `test_mcp_derived_default_tools_match_published_fastmcp_schemas` in `tests/test_pydantic_ai_mcp.py` verifying that every MCP-derived tool in `get_default_tools()` has a `Tool.from_function` JSON schema identical to FastMCP's published `parameters` schema, emits no `PydanticJsonSchemaWarning`, and executes `hydrate_tool_domain` without an MCP session.
- [x] Verify `tests/test_ai_cmd.py::test_ai_extended_commands` and `tests/test_ai_cmd.py::test_ai_token_count_route_pipeline_bundle` pass under `-W error::pydantic.json_schema.PydanticJsonSchemaWarning`.
