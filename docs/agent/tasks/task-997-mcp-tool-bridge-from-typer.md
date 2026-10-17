# Task: Generate FastMCP Tool Bridge from Typer App (#997)

**Issue**: [#997](https://github.com/dan-petty/devops-cli/issues/997)
**Status**: Done
**Feasibility**: Verified against Click/Typer app command metadata introspection, parameter signature generation with `pydantic.Field` annotations, and `fastmcp` 2.14.5 dynamic tool registration in the local environment.

## Summary

Replaced 147 hand-written argv construction wrappers in `src/devops_cli/ai/mcp/server.py` with dynamic FastMCP tool generation driven by `CONST_MCP_EXPOSURE_TABLE` (146 commands) and `src/devops_cli/ai/mcp/generator.py`. Retained exactly 5 hand-written tools, removed dead functional handlers in `dispatcher.py` and test-detecting branches in `server.py`, derived canonical tool names with zero legacy shims, and added comprehensive schema-matching and exhaustive CLI coverage tests.

## Deliverables

- [x] Defined `CONST_MCP_EXPOSURE_TABLE` (146 commands) and `CONST_MCP_COMMAND_EXCLUSIONS` (302 commands) in `src/devops_cli/config/constants.py` partitioning all 448 leaf CLI commands without overlap.
- [x] Implemented `src/devops_cli/ai/mcp/generator.py` to introspect Click/Typer parameters, map types and default values, validate against argument hyphen injection, and dynamically register tools onto FastMCP with $M \le 10$ and nesting depth $\le 5$.
- [x] Rewrote `src/devops_cli/ai/mcp/server.py` (~400 lines vs 3244 previously), retaining exactly 5 hand-written tools (`hydrate_tool_domain`, `security_intel_package`, `security_intel_network`, `scan_uv_audit`, `k8s_tempo_info`), 20 dynamic system resources, and 4 prompt templates.
- [x] Deleted dead `register_handler`, `_functional_handlers`, and `_check_functional_handlers` from `InProcessDispatcher` in `src/devops_cli/ai/mcp/dispatcher.py`, and removed test-detecting `hasattr(run_subprocess, "assert_called")` branch from `server.py`.
- [x] Derived canonical tool names from `"_".join(command_path).replace("-", "_")` without backwards compatibility aliases or legacy shims.
- [x] Decoupled MCP package initialization in `src/devops_cli/ai/mcp/__init__.py` using lazy `__getattr__` with dynamic module import to prevent circular import cycles.
- [x] Added parametrised schema property validation and argv parsing test across all exposure table entries, and exhaustive recursive coverage test asserting zero unclassified CLI commands.
- [x] Regenerated `docs/MCP_TOOLS.md` and exported MCP tool schemas with `devops docs generate` and `devops mcp export-schemas`.
