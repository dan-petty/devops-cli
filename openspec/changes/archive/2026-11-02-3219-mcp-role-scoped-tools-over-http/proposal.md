# Proposal

## Why

Issue #3219. The jobs of the roadmap pipeline (planning, implementation, review) get their tools from code in the job container. A tool that the image does not carry (a scanner, a cluster read, a GitHub read) cannot be used. The owner wants tool sets that depend on the job role, served by an MCP server that the jobs reach through the LiteLLM gateway.

`devops mcp serve` cannot do this today. It has `stdio` and `sse` only, and `sse` has no authentication. It advertises one process-wide tool set (`_HYDRATED_DOMAINS` in `ai/mcp/server.py`), so a `hydrate_tool_domain` call of one caller changes the list of every caller. It holds 146 tools, and 44 of them are not read-only.

The owner decided on 2026-11-02 (comments on #3219): jobs reach the server through LiteLLM; the server is reachable only from LiteLLM and checks a bearer token that is a mounted secret (no `TokenReview`); a secret is never a tool parameter; the `ops` role stays off and no job role gets it. The client in the jobs (#3221) and the deployment and LiteLLM configuration (#3220) are other issues.

## What Changes

- A new transport `streamable-http` of `devops mcp serve`. It serves one endpoint for each job role: `/planning/mcp`, `/implementation/mcp` and `/review/mcp`. Each path is a separate `FastMCP` server that holds only the tools of its role, so the role of a connection is the path, which the deployment chooses, and not anything the model sends. A tool outside the role does not exist on the path, so a call by name fails. The endpoints are stateless and answer in JSON, so no connection keeps state that another sees. `ops` has no endpoint.
- A job role holds a tool only when `roles.py` names it and the exposure table marks it read-only (`readOnlyHint`). The tables name no tool that reads or writes a path that a model gives. `planning` has 28 tools, `implementation` 17 and `review` 16. The `ops` role (every tool but `hydrate_tool_domain`) exists for in-process use and has no network path.
- A role server has no resource, no prompt, no domain gate and no `hydrate_tool_domain`, so the process-wide `_HYDRATED_DOMAINS` is never read by a network connection.
- A new credential `mcp.token` (`DEVOPS_CLI_MCP_TOKEN`). The transport refuses to start without it, and refuses a token of fewer than 32 characters. A non-loopback host needs `--allow-remote`, as for `sse`. `--dry-run` refuses the same things.
- Every request needs `Authorization: Bearer <token>`. The server compares the SHA-256 digests with `hmac.compare_digest` before any tool runs and answers 401 otherwise.
- The server logs the role and the tool name of each call, and no argument.
- `check_sse_bind` becomes `check_bind` and covers both network transports; the error `security_sse_non_loopback` becomes `security_non_loopback`. `ArgumentContractMiddleware` takes the server whose tools it reads.
- `SECURITY.md` states the facts under rule 11. The rule on secrets as tool parameters is #3222 and is not added here.
- The change alters a command option and the behavior of a service, so it carries a spec delta: a new capability `mcp-role-server`, and a modified requirement `server-request-plans` of `command-dry-run-class`.
- The change fits one pull request.

### Out of scope

- The deployment, the NetworkPolicy and the `mcp_servers` section of LiteLLM (#3220).
- The client in the jobs (#3221).
- The rule and the test on secrets in tool schemas (#3222).
- A limit on the number of tool calls of a job and the Job name in the audit line. LiteLLM sits between the job and the server, so the server cannot see the Job. The virtual key carries the budget.
- A path check for the tools that take a path. The role tables leave those tools out until a path helper confines them.

## Capabilities

### New Capabilities

- `mcp-role-server`: the role endpoints, the tool set of a role, the bearer token and the audit line of the streamable HTTP transport.

### Modified Capabilities

- `command-dry-run-class`: MODIFIED `server-request-plans`, so the dry run of `mcp serve` also covers `streamable-http`.

## Impact

- Code: new `src/devops_cli/ai/mcp/roles.py` and `src/devops_cli/ai/mcp/remote.py`; `src/devops_cli/ai/mcp/server.py` (`check_bind`, `transport_token`, `run_mcp_server`, `ArgumentContractMiddleware`); `src/devops_cli/commands/mcp.py`; `src/devops_cli/config/env.py` and `settings.py` (the credential); `src/devops_cli/lang/en/errors.py`, `messages.py` and `help.py`.
- Documents: `SECURITY.md`, `docs/CLI_REFERENCE.md`, `docs/commands/mcp.md`, `docs/ENV_VARS.md` (generated).
- Tests: `tests/ai/mcp/test_mcp_roles.py`, `tests/ai/mcp/test_mcp_http.py`, `tests/commands/test_mcp_serve.py`, `tests/security/test_config_declarations.py`, `tests/ai/mcp/test_fastmcp_contracts.py`.
- No change in `config/constants.py`.

## Feasibility

Checked on 2026-11-02 on `main` at the commit of release 0.46.0 (a plain clone, Python 3.14.6, `fastmcp==4.1.2` from `uv.lock`). The pieces were read in the installed package and then run.

FastMCP 4.1.2 (`.venv/lib/python3.14/site-packages/fastmcp`):

- `FastMCP.http_app(path, transport="streamable-http", json_response, stateless_http, ...)` in `server/mixins/transport.py` builds a Starlette app with `create_streamable_http_app` (`server/http.py`). `FastMCP(auth=...)` takes an `AuthProvider`. With an `auth`, the route of the endpoint is wrapped in `RequireAuthMiddleware` behind `AuthenticationMiddleware(BearerAuthBackend)` (`http.py`, "if auth:" branch). A request with no or a wrong token is answered 401 with `WWW-Authenticate: Bearer`. With `auth=None` the route has no check, so the server must never be built without it.
- `TokenVerifier` (`server/auth/auth.py`) needs only `async verify_token(token) -> AccessToken | None`. `StaticTokenVerifier` (`server/auth/providers/jwt.py`) looks the token up in a dict and its docstring says "Never use this in production", so the change adds a verifier with a constant-time comparison.
- `FastMCP.mount` (`server/server.py`) forwards to the mounted server, and its docstring says "its middleware chain is invoked for all operations". The stdio server's `DomainGateMiddleware` reads the global `_HYDRATED_DOMAINS`, so mounting it would leak the global into a role. The change builds one server for each role from the registered `Tool` objects (`add_tool`) instead.
- `fastmcp.utilities.lifespan.combine_lifespans` joins the lifespans of the role apps, and FastAPI (a direct dependency) mounts the apps. `starlette` is a transitive dependency, so the change does not import it.
- The Host and Origin guard of FastMCP is off by default (`http_host_origin_protection = False` in `settings.py`). The change leaves it off: the server is for a gateway that sends its own `Host`, and the bearer token is the check.

Runs:

- `uv run python` over `asyncio.run(mcp._list_tools())`: 146 tools, 102 with `readOnlyHint` true and 44 without. The read-only set holds `vault_get`, `valkey_get`, `config_show`, `config_output`, `ssh_audit`, `ai_read` and `ai_ast_graph --output_path`. So the read-only flag alone is not enough for a network role, and the change adds the name tables.
- A probe with `fastapi.testclient.TestClient` over `build_http_app`: `/planning/mcp` lists 28 tools and `/review/mcp` 16; `/ops/mcp`, `/mcp` and `/` give 404; no token and a wrong token give 401; `tools/call` of `gh_issues_create` on `/planning/mcp` gives `Unknown tool`.
- A real socket on loopback with `devops mcp serve --transport streamable-http --port 18765`: curl without a token gives 401, with a wrong token 401, with the token 200 and the tool list. Without `DEVOPS_CLI_MCP_TOKEN` the command prints the refusal and starts nothing.

LiteLLM `v1.103.0` (the sdist of `litellm==1.103.0` from PyPI, read only, nothing run; files under `litellm/proxy/_experimental/mcp_server/` and `litellm/experimental_mcp_client/`). For #3220:

- `mcp_servers` entries of `config.yaml` take `url`, `transport` (`sse`, `http` or `stdio`; the default is `http`), `auth_type`, `authentication_token`, `static_headers`, `extra_headers`, `allowed_tools`, `disallowed_tools` and `access_groups` (`MCPServerConfig` in `mcp_server_manager.py`).
- The `http` transport is `mcp.client.streamable_http.streamable_http_client(url=server_url, http_client=...)` (`client.py`, `_create_transport_context`). The `url` is used as it is, so it must be `.../planning/mcp`, with the role in the path. With `auth_type: bearer_token` the client sends `Authorization: Bearer <authentication_token>` (`_get_auth_headers`).
- A virtual key is limited to servers and tools through its object permission (`get_allowed_mcp_servers` and `get_allowed_tools_for_server` in `auth/user_api_key_auth_mcp.py`), and the `x-mcp-servers` header chooses servers. So one `mcp_servers` entry for each role path, and a key that may use one of them, gives the role.
- Not verified: that the pinned image runs this as read, that `authentication_token` takes an `os.environ/` reference, and how the standard client treats the 405 that this server returns for the optional `GET` stream. The change serves `POST` and `DELETE` only (stateless). #3220 must run it.

Premises of the issue that changed: the `TokenReview` check is replaced by the bearer token of the owner's decision. "ops stays off" is kept by giving `ops` no endpoint. "Each role is a list from the exposure table with the read-only flag deciding" is not enough alone (see the run above), so a name table limits each job role.

## Existing Tool Considered

FastMCP 4.1.2 is the tool and covers the transport, the auth hook, the bearer middleware and the lifespan. The change builds only what it does not cover: the role tables, the constant-time verifier and the composition of the role apps. No open library gives role-scoped tool sets from a Typer exposure table. Written cost: about 150 000 tokens and 5 hours to build and test it; about 5 000 tokens a year to keep, because a table changes when a tool is added; about 20 000 tokens when FastMCP changes its HTTP API. It deletes `check_sse_bind` and the error `security_sse_non_loopback`, which `check_bind` replaces.
