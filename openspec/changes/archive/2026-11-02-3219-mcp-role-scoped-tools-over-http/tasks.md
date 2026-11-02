# Tasks

## 1. The tool set of each role

- [x] 1.1 Write failing tests in `tests/ai/mcp/test_mcp_roles.py` for the scenarios of "Two roles list different tools", "A mutating tool called by name", "A tool outside the role", "A table names a tool that does not exist" and "Hydration does not leak"
  - Verification: `uv run devops ci test tests/ai/mcp/test_mcp_roles.py` (fails on the base: the modules `roles` and `remote` do not exist)
- [x] 1.2 Add `src/devops_cli/ai/mcp/roles.py` (the role names, the tables and `tools_for_role`) and `build_role_server` in `src/devops_cli/ai/mcp/remote.py`, and let `ArgumentContractMiddleware` take the server whose tools it reads
  - Verification: `uv run devops ci test tests/ai/mcp/test_mcp_roles.py tests/ai/mcp/test_fastmcp_contracts.py`

## 2. The bearer token and the HTTP endpoints

- [x] 2.1 Write failing tests in `tests/ai/mcp/test_mcp_http.py` for the scenarios of "A path that is no job role", "A wrong token", "No token", "A call is logged", "No token" (start) and "A short token"
  - Verification: `uv run devops ci test tests/ai/mcp/test_mcp_http.py` (fails on the base: the module `remote` does not exist)
- [x] 2.2 Add the credential `mcp.token` to `config/env.py` and `get_mcp_token` to `config/settings.py`, and add `BearerTokenVerifier`, `RoleAuditMiddleware`, `build_http_app` and `serve_streamable_http` to `remote.py`
  - Verification: `uv run devops ci test tests/ai/mcp/test_mcp_http.py tests/security/test_config_declarations.py`

## 3. The transport option of the command

- [x] 3.1 Write failing tests in `tests/commands/test_mcp_serve.py` for the scenarios of "Dry run on mcp serve over streamable-http" and "Dry run on mcp serve over streamable-http without a token"
  - Verification: `uv run devops ci test tests/commands/test_mcp_serve.py` (fails on the base: the transport is invalid)
- [x] 3.2 Replace `check_sse_bind` by `check_bind` in `server.py`, add `transport_token`, start `streamable-http` from `run_mcp_server`, accept the transport in `commands/mcp.py`, rename the error `security_sse_non_loopback` to `security_non_loopback`, and add the messages and help texts
  - Verification: `uv run devops ci test tests/commands/test_mcp_serve.py tests/ai/mcp`

## 4. The documents

- [x] 4.1 State the facts under rule 11 of `SECURITY.md` and regenerate the reference with `devops docs generate --sync-readme`
  - Verification: `uv run devops docs check`

## 5. The archive

- [x] 5.1 Archive the change
  - Verification: `uv run devops openspec archive 3219-mcp-role-scoped-tools-over-http`

## Workflow follow-up

- Work the item will not do: the MCP Deployment, its NetworkPolicy and the `mcp_servers` section of LiteLLM, in #3220.
- Work the item will not do: the client in the jobs, in #3221.
- Work the item will not do: the rule and the test on secrets in tool schemas, in #3222.
- Work the item will not do: a path check for the tools that take a path, and a limit on the tool calls of a job on the server. No issue plans them yet.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
