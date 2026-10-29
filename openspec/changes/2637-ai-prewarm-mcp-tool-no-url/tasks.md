# Tasks

## 1. The MCP prewarm tool publishes no URL

- [x] Add failing tests: the schema of the tool holds no URL. A call that gives a URL fails and dials nothing. The tool prewarms each configured server at the configured level. `--url` of the command still reaches the host that a person types
  - Verification: `uv run devops ci test tests/test_ai_prewarm.py`
- [x] Give `ai prewarm` an entry in `_PATH_PARAM_RESTRICTIONS` that leaves out `url`
  - Verification: `uv run devops ci test tests/test_ai_prewarm.py tests/test_mcp.py tests/test_fastmcp_contracts.py`
- [x] Regenerate the tool documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2637-ai-prewarm-mcp-tool-no-url`

## Workflow follow-up

- The other MCP tools that publish a URL option are not part of this change. #2638 covers `ai_benchmark` and #2639 covers `vault_status`.
- The paragraph under principle 11 of `SECURITY.md` says that the Valkey commands are not MCP tools. Six of them are. #2670 covers this.
- The output of `devops ai prewarm` and `devops ai preload` names each Ollama server by its configured URL. The metric `AI_PREWARMS_TOTAL` also has an unbounded `model` label. #2676 covers both.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
