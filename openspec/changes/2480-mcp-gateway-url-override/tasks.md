# Tasks

## 1. The MCP gateway tools publish no URL

- [x] Add failing tests: the schema of each tool holds no URL. A call that gives a URL fails, dials nothing and puts no key on the wire. Each tool dials its configured service at the configured level
  - Verification: `uv run devops ci test tests/test_ai_gateway.py`
- [x] Give `ai_gateway_status`, `ai_gateway_routes` and `ai_gateway_probe_backend` an entry in `_PATH_PARAM_RESTRICTIONS`, so that they publish only `provider` or `backend`
  - Verification: `uv run devops ci test tests/test_ai_gateway.py tests/test_mcp.py tests/test_fastmcp_contracts.py`
- [x] Regenerate the tool documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. The AI API key goes only to the configured gateway

- [x] Add failing tests: a request of the model query carries the key only for the origin of a configured gateway, through `list_routes`, `fetch_model_info` and `tune_pool`. A refusal by another gateway says that it got no key. `devops ai gateway routes --gateway-url` of another origin sends no key
  - Verification: `uv run devops ci test tests/test_ai_gateway.py`
- [x] Attach the key in `_query_model_info` only for a configured origin, and raise the refusal that says the gateway got no key. Pass the `ai_config` of the router and of the OpenAI client
  - Verification: `uv run devops ci test tests/test_ai_gateway.py tests/test_ai_gateway_tune.py tests/test_thinking_providers.py tests/test_http_egress.py`
- [x] Say in the help of `--gateway-url` for `routes` and `tune` that only the configured gateway gets the key, and regenerate the command documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 3. The rule is in the security policy

- [x] Add principle 11 to `SECURITY.md`. A URL from a model is untrusted input for an MCP tool. A credential goes only to the origin that the configuration names
  - Verification: `uv run devops docs check`

## 4. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2480-mcp-gateway-url-override`

## Workflow follow-up

- The other MCP tools that publish a URL option are not part of this change. Design.md lists them as open exceptions. #2634 covers `valkey_*`, #2635 covers `k8s_logs`, #2637 covers `ai_prewarm`, #2638 covers `ai_benchmark` and #2639 covers `vault_status`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
