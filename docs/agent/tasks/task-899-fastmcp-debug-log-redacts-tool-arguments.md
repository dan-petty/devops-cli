# Task: FastMCP's Debug Log of Tool Calls Never Records Argument Values (#899)

**Issue**: [#899](https://github.com/dan-petty/devops-cli/issues/899)
**Status**: Done
**Milestone**: v0.2.30
**Priority**: priority/p2-medium
**Scope**: scope/mcp

## Description

FastMCP logs every `tools/call` and `prompts/get` at DEBUG on the
`fastmcp.server.mixins.mcp_operations` logger, as `Handler called: call_tool %s with %s` and
`Handler called: get_prompt %s with %s`, with the call's arguments as the second argument. At
FastMCP's default INFO level the record is never written, but with `FASTMCP_LOG_LEVEL=DEBUG` a
`vault_set` call wrote its `key_values` to stderr, and any other secret argument with it. #862's
log filter did not cover that logger.

- `ArgumentValueLogFilter` (`src/devops_cli/ai/mcp/argument_contract.py`) replaces every mapping
  argument of a record with `<redacted>` (`CONST_REDACTED_LOG_VALUE`) and keeps the record, so the
  log still names the tool or prompt: `Handler called: call_tool vault_set with <redacted>`. The
  server attaches it to `fastmcp.server.mixins.mcp_operations` alone
  (`CONST_FASTMCP_OPERATIONS_LOGGER` in `src/devops_cli/config/constants.py`).
- The whole mapping is replaced rather than each value, because an undeclared parameter's name is
  the caller's own text too: #862 masks and cuts such a name before a refusal echoes it, and a
  `ghp_` token sent as a parameter name would otherwise reach the log.
- #862's `RejectedInputLogFilter` on `fastmcp.server.server` is removed, with
  `CONST_FASTMCP_SERVER_LOGGER`. Since fastmcp 4.0.11 (#1184), FastMCP logs a refused call's
  pydantic error count and types (`include_input=False`), never the input, so the filter matched
  nothing. Nothing is attached to that logger now: a mapping filter there would redact the error
  summary, which is that warning's only diagnostic.
- The mcp SDK's SSE transport DEBUG logs (`mcp.server.sse`) are not a FastMCP logger and format
  their message before logging, so a record-argument filter cannot reach them; they are outside
  this item.

## Acceptance Criteria

- [x] With every FastMCP logger at DEBUG, a `vault_set` call carrying a sentinel value leaves no
  log record containing it. `test_no_tool_argument_reaches_a_debug_record`
  (`tests/test_fastmcp_contracts.py`) captures the `fastmcp` logger tree at DEBUG through
  `fastmcp.Client(mcp)`, finds `Handler called: call_tool vault_set`, so the record was written,
  and finds no sentinel, with the handler run once. Before the filter the record read
  `call_tool vault_set with {'path': 'secret/app', 'key_values': ['API_KEY=sentinel-4b1d']}`.
- [x] The `fastmcp_log` fixture now captures every FastMCP logger at DEBUG, so
  `test_a_strict_refusal_is_rendered_like_a_schema_refusal` also holds the DEBUG argument record
  to no `4242`, which it failed before the filter. `test_no_rejected_input_reaches_a_log_record`
  holds FastMCP's own refusal warning to no rejected input, with no filter on that logger.
- [x] `uv run devops ci` passes.
