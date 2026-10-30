# Tasks

## 1. The MCP benchmark tool takes no file path

- [x] Add failing tests: the schema of the tool holds no `output`, `document` and `code`. A call that gives one fails, changes no file in a real directory and sends no request
  - Verification: `uv run devops ci test tests/test_ai_benchmark_mcp_tool.py`
- [x] Leave `output`, `document` and `code` out of the entry of `ai benchmark` in `_PATH_PARAM_RESTRICTIONS`
  - Verification: `uv run devops ci test tests/test_ai_benchmark_mcp_tool.py tests/test_ai_benchmark.py tests/test_embedding_benchmark.py tests/test_mcp.py tests/test_fastmcp_contracts.py`
- [x] Reword the help text of `--samples` so that it names no flag, state the path rule in `SECURITY.md` principle 11, and add a contract test that no tool text names a flag that the tool leaves out
  - Verification: `uv run devops ci test tests/test_fastmcp_contracts.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2704-mcp-benchmark-no-path-options`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
