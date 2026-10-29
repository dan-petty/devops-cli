# Tasks

## 1. The MCP gateway tools publish no URL

- [x] Add failing tests: the schema of each of the three tools holds no URL; a call that gives a URL fails, dials nothing and puts no key on the wire; `ai_gateway_status` dials the configured gateway at the configured level
  - Verification: `uv run devops ci test tests/test_ai_gateway.py`
- [x] Give `ai_gateway_status`, `ai_gateway_routes` and `ai_gateway_probe_backend` an entry in `_PATH_PARAM_RESTRICTIONS`, so that they publish only `provider` or `backend`
  - Verification: `uv run devops ci test tests/test_ai_gateway.py tests/test_mcp.py tests/test_fastmcp_contracts.py`
- [x] Regenerate the tool documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`

## 2. The AI API key goes only to the configured gateway

- [x] Add failing tests: a request of `list_routes` carries the key only for the configured origin (the same path, another path, another spelling, another host, another port, another scheme, user information, no configured gateway); `devops ai gateway routes --gateway-url` of another origin sends no key; a refusal by another gateway says that it got no key. Give the three route discovery tests that need the key a configured gateway
  - Verification: `uv run devops ci test tests/test_ai_gateway.py`
- [x] Send the key from `GatewayRouter.list_routes` only to the origin of the configured gateway, and raise the refusal that says the gateway got no key
  - Verification: `uv run devops ci test tests/test_ai_gateway.py tests/test_http_egress.py tests/test_ai_gateway_portkey.py`
- [x] Say in the help of `devops ai gateway routes --gateway-url` that only the configured gateway gets the key, and regenerate the command documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`

## 3. The rule is in the security policy

- [x] State in `SECURITY.md` that a URL from a model is untrusted input for an MCP tool, and that a credential goes only to the origin that the configuration names
  - Verification: `uv run devops ci docs`

## 4. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2480-mcp-gateway-url-override`

## Workflow follow-up

- The other MCP tools that publish a URL option are not part of this change. #2634 covers the `valkey_*` tools, which send the Valkey password to the URL of the caller. #2635 covers `k8s_logs`, which dials a Loki URL of the caller at the private level and returns the answer.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
