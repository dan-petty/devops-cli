# Tasks

## 1. The MCP benchmark tool takes no server URL

- [x] Add failing tests: the schema of the tool holds no `servers`. A call that gives `servers` or a `model@url` entry fails and dials nothing. The tool benchmarks on the configured server at the configured level. `--servers` and `--models model@url` of the command still reach the host that a person types
  - Verification: `uv run devops ci test tests/test_ai_benchmark_mcp_tool.py`
- [x] Give `ai benchmark` an entry in `_PATH_PARAM_RESTRICTIONS` that leaves out `servers`, and refuse a `model@url` entry of `models` before dispatch
  - Verification: `uv run devops ci test tests/test_ai_benchmark_mcp_tool.py tests/test_ai_benchmark.py tests/test_mcp.py tests/test_fastmcp_contracts.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2638-mcp-benchmark-no-server-url`

## Workflow follow-up

- The other MCP tool that publishes a URL option is not part of this change. #2639 covers `vault_status`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
