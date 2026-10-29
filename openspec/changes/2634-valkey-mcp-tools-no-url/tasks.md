# Tasks

## 1. The MCP Valkey tools publish no URL

- [x] Add failing tests: the schema of each tool holds no URL. A call that gives a URL fails and opens no connection. Each tool reaches the configured server with its password. Make `serving_valkey` return at once when no client connects
  - Verification: `uv run devops ci test tests/test_valkey.py`
- [ ] Give each of the six Valkey commands an entry in `_PATH_PARAM_RESTRICTIONS` that leaves out `url`
  - Verification: `uv run devops ci test tests/test_valkey.py tests/test_mcp.py tests/test_fastmcp_contracts.py`
- [ ] Regenerate the tool documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2634-valkey-mcp-tools-no-url`

## Workflow follow-up

- The other MCP tools that publish a URL option are not part of this change. #2635 covers `k8s_logs`, #2637 covers `ai_prewarm`, #2638 covers `ai_benchmark` and #2639 covers `vault_status`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
