# Tasks

## 1. The MCP Valkey tools publish no URL

- [x] Add failing tests: the schema of each tool holds no URL. A call that gives a URL fails and opens no connection. Each tool reaches the configured server with its password. Make `serving_valkey` return at once when no client connects
  - Verification: `uv run devops ci test tests/test_valkey.py`
- [x] Give each of the six Valkey commands an entry in `_PATH_PARAM_RESTRICTIONS` that leaves out `url`
  - Verification: `uv run devops ci test tests/test_valkey.py tests/test_mcp.py tests/test_fastmcp_contracts.py`
- [x] Regenerate the tool documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. The accepted case is recorded

- [x] Add a test that pins the case: `devops valkey ping --url` sends the password to the host that a person types
  - Verification: `uv run devops ci test tests/test_valkey.py`
- [x] Add a paragraph under principle 11 of `SECURITY.md` and a note in the docstring of `_resolve_client`
  - Verification: `uv run devops docs check`

## 3. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2634-valkey-mcp-tools-no-url`

## Workflow follow-up

- The other MCP tools that publish a URL option are not part of this change. #2635 covers `k8s_logs`, #2637 covers `ai_prewarm`, #2638 covers `ai_benchmark` and #2639 covers `vault_status`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
