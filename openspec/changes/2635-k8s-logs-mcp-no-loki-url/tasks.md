# Tasks

## 1. The MCP tool k8s_logs publishes no Loki URL

- [x] Add failing tests: the schema of `k8s_logs` holds no `loki_url`. A call that gives a loopback or private `loki_url` fails, dials nothing and returns no answer text. A call with no URL sends the query to the default Loki. `devops k8s logs --loki-url` still dials the URL of the person
  - Verification: `uv run devops ci test tests/test_k8s_logql.py`
- [ ] Give `("k8s", "logs")` an entry in `_PATH_PARAM_RESTRICTIONS` that leaves out `loki_url`
  - Verification: `uv run devops ci test tests/test_k8s_logql.py tests/test_mcp.py tests/test_fastmcp_contracts.py`
- [ ] Regenerate the tool documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2635-k8s-logs-mcp-no-loki-url`

## Workflow follow-up

- The `loki.url` setting that the error texts name does not exist, and the command dials a localhost default. This is not part of this change. #2651 covers it.
- The other MCP tools that publish a URL option are not part of this change. #2637 covers `ai_prewarm`, #2638 covers `ai_benchmark` and #2639 covers `vault_status`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
