# Task 839: MCP Command Tools Protocol Stream Isolation and Failure Semantics

**Issue**: [#839](https://github.com/dan-petty/devops-cli/issues/839)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: type/bug, scope/ai

---

## 1. Description & Objectives

Previously, in-process FastMCP tool execution allowed child processes to inherit and write directly to standard file descriptors (OS fd 1 and fd 2), corrupting the JSON-RPC stdio protocol stream and breaking protocol parsers on MCP clients. In addition, command tools returning non-zero exit codes reported results as raw text strings without setting MCP protocol-level error status (`isError: true`), and `ci_run` was limited in check arguments and timeout margins.

This deliverable resolves the defect and hardens MCP command tools:
- **Child Process File Descriptor Isolation**: Implemented `_isolate_child_stdio()` context manager in `src/devops_cli/ai/mcp/dispatcher.py` to redirect OS fds 1 and 2 to temporary files during in-process command execution. Captured output from both child processes and Python stdout/stderr is merged safely in memory without polluting the protocol stream.
- **Deterministic Dispatcher Fallback Contract**: Updated `CommandDispatcher.dispatch()` and its sub-dispatchers to return `"Success"` only on exit code 0 when output is empty, and `"no output captured"` on non-zero exit codes.
- **FastMCP Protocol Error Semantics (`ToolError`)**: Updated `_run_mcp_cmd` in `src/devops_cli/ai/mcp/server.py` to raise `fastmcp.exceptions.ToolError` on non-zero exit codes, carrying masked and bounded output (bounded to `CONST_MCP_MAX_COMMAND_OUTPUT_CHARS = 4000` with `DEFAULT_TRUNCATION_SUFFIX`). This ensures clients see `isError: true` with clean diagnostic details.
- **Expanded `ci_run` Gate Coverage & Budget Margin**: Updated `ci_run` tool to accept any check name defined by the gate (`all`, `test`, `lint`, `format`, `typecheck`, `audit`, `security`, `actionlint`, `docs`, `uv-check`, `lockfile`, `outdated`, `devcontainer`), invoke `uv run devops ci --check <name>`, and derive its timeout from `CONST_CI_TEST_BUDGET_SECONDS + CONST_CI_TEST_BUDGET_MARGIN_SECONDS` (360.0s). Expanded the docstring detailing every check in the gate.
- **Verification**: Fast unit tests in `tests/test_fastmcp_in_process.py` and `tests/test_mcp.py` verify stdio isolation with `capfd`, `ToolError` propagation, and `ci_run` argument contracts in < 1s.

---

## 2. Acceptance Criteria

- [x] In-process dispatch never lets child processes write directly to OS fd 1 or fd 2.
- [x] Dispatcher returns `"Success"` on exit code 0 when output is empty, and `"no output captured"` on non-zero exit codes.
- [x] Command failure raises FastMCP `ToolError` with bounded, masked output, yielding `isError: true` to callers.
- [x] `ci_run` invokes `devops ci --check`, supports all 12 gate checks, has budget margin timeout, and documents all checks in docstring.
- [x] Fast tests verify behavior in < 1s using `capfd` and unit mocks.
- [x] Changelog fragment `changelog.d/839.md` authored.
- [x] Gated CI quality checks pass in `uv run devops ci`.

---

## 3. Deliverables

- [x] `src/devops_cli/config/constants.py`: Added `CONST_MCP_MAX_COMMAND_OUTPUT_CHARS` and `CONST_CI_TEST_BUDGET_MARGIN_SECONDS`.
- [x] `src/devops_cli/ai/mcp/dispatcher.py`: Implemented `_isolate_child_stdio()`, `_read_stream()`, and fallback output contracts.
- [x] `src/devops_cli/ai/mcp/server.py`: Added output bounding, `ToolError` on non-zero exit, and expanded `ci_run` parameters and documentation.
- [x] `tests/test_fastmcp_in_process.py`: Added tests for fd isolation with `capfd`, failure status/diagnostic propagation, and `ci_run` parameters.
- [x] `tests/test_mcp.py`: Updated error branch assertions for `ToolError`.
- [x] `changelog.d/839.md`: Changelog fragment.
- [x] `docs/agent/tasks/task-839-mcp-command-tools-protocol-isolation.md`: Task tracking file.
