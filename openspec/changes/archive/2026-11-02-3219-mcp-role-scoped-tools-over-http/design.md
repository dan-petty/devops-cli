# Design

## Decisions

### One `FastMCP` server for each role, and the path is the role

`build_role_server(role)` creates a `FastMCP` and adds only the `Tool` objects of the role, taken from the registry of the stdio server. `build_http_app` makes the streamable HTTP app of each job role and mounts it at `/<role>`. The deployment picks the role by the URL that it gives to the gateway. A tool that the role does not hold is not registered on that server, so the call fails as an unknown tool and no handler runs.

Rejected: one server with a role in a context variable and a filter in a middleware. A forgotten code path would then serve a tool outside the role. Here the registry is the boundary.

Rejected: `FastMCP.mount` of the stdio server into each role server. `mount` runs the middleware chain of the mounted server (the docstring in `server/server.py` says so), and `DomainGateMiddleware` reads the process-wide `_HYDRATED_DOMAINS`. A hydration on one connection would change the list of another. Rejected also: moving `_HYDRATED_DOMAINS` into session state. The role endpoints need no hydration, because the role is the tool set.

### A job role is a name table cut by the read-only flag

A role holds a tool when `roles.py` names it and the exposure table marks it read-only. The run of the registry shows why the flag alone is not enough: 102 tools are read-only, among them `vault_get`, `valkey_get`, `config_show`, `ssh_audit` and `ai_read`, and several take a path (`ai_ast_graph --output_path`, `k8s_security_stream --output`, `gh_pages_verify --root_dir`). On the server such a path is a path of the server. The tables name the GitHub reads, the security intelligence lookups and the cluster reads, and none of the path tools. A new tool is in no job role until a person adds its name, which is the "table that changes when a tool is added" of the issue. A name that no tool carries makes the server refuse to start, so a renamed command cannot shrink a role without notice.

The tables are distinct: `planning` adds the cluster reads, `implementation` adds `pr_describe`, and `review` holds the GitHub reads and the lookups. The split is a judgement. A person edits the tables when a job needs more.

Rejected: roles as tags on `CONST_MCP_EXPOSURE_TABLE`. Every row would change, in the file that another open pull request edits, for a list that only the MCP package reads (`CONTRIBUTING.md`: a table sits beside its one owner).

Rejected: the same read-only set for all three job roles. It would serve `vault_get` and `ai_read` to a model over the network.

### `ops` is the whole catalogue and has no endpoint

`tools_for_role("ops", ...)` returns every tool but `hydrate_tool_domain`. `JOB_ROLES` is the only list that `build_http_app` reads, so `/ops/mcp` is a 404. The owner's decision keeps `ops` off. A test fails if an `ops` path answers.

### The bearer token is one credential, checked before any tool

The owner decided that the server checks a bearer token that is a mounted secret. `BearerTokenVerifier` is a `TokenVerifier` that compares SHA-256 digests with `hmac.compare_digest`, so neither the content nor the length of the token shows in the time of a refusal. FastMCP's own `RequireAuthMiddleware` answers 401 before the handler. The credential `mcp.token` is a keyring credential with the variable `DEVOPS_CLI_MCP_TOKEN`, as `mattermost.command_token` is. It is not a settings field, so the config file cannot hold it.

Rejected: `StaticTokenVerifier`. It uses a dict lookup, and its docstring says that it is for tests.
Rejected: the role in the token. The owner chose one token for the gateway, and the gateway's virtual key limits the role. Two tokens would add a second secret for no check that the path does not give.
Rejected: `TokenReview` of the issue body. The owner replaced it, because the caller is LiteLLM, which has no Kubernetes identity.

### Stateless, JSON answers

`stateless_http=True` and `json_response=True`. Each request makes a fresh transport, so two jobs share no session, and a replica needs no session affinity. The server sends no notification, so nothing needs the `GET` stream. A gateway that insists on the stream would get 405, which the MCP specification allows.

### Resources and prompts are not served

The resources of the stdio server run `devops` commands (`config show`, `vault status`) with no role check. A role server registers only tools.

### Start refuses what is unsafe

`devops mcp serve --transport streamable-http` raises `SecurityError` for a missing or short token and for a non-loopback host without `--allow-remote`. The dry run runs the same checks first, so it refuses what the start refuses. `check_bind` replaces `check_sse_bind` for both network transports.
