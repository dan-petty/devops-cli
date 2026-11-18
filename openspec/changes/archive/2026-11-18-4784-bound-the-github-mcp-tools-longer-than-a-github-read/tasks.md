# Tasks

## 1. Behavior

- [x] 1.1 Write the failing chain test for the `gh` and `pr` MCP rows
  - Verification: `$ uv run devops ci test tests/github/test_github_session_timeouts.py`
- [x] 1.2 Add `CONST_MCP_GITHUB_TOOL_TIMEOUT_SECONDS` and set every `gh` and `pr` row to it
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_tool_argv.py`

## 2. Documents

- [x] 2.1 Add the requirement to the `mcp-tool-timeout` capability
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
