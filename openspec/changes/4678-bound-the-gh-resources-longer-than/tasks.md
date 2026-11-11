# Tasks

## 1. Behavior: the bound of the gh resources and the chain of an MCP read

- [x] 1.1 Add the failing tests: each `resource://gh/` resource dispatches its command with `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`, and the chain test holds the chain of a `resource://gh/` resource next to the chain of the implement job
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_prompts_and_resources.py tests/github/test_github_session_timeouts.py`
- [x] 1.2 Give the four `resource://gh/` resources of `src/devops_cli/ai/mcp/server.py` the bound `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`, and name the calls around a read in the comment of `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS`
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_prompts_and_resources.py tests/github/test_github_session_timeouts.py`

## 2. Documents

- [x] 2.1 Name the calls that the read bound is shorter than in ADR 0006 (Client), and correct the rejected alternative of the MCP tool call in the archived design of #4626
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #4784 gives the MCP tools of `CONST_MCP_EXPOSURE_TABLE` that read GitHub a bound that is longer than a session read.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
