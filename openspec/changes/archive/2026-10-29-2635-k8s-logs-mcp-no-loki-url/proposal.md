# Proposal

## Why

Issue #2635. The MCP tool `k8s_logs` published the option `loki_url`. The model that calls the tool fills it in. `execute_loki_query` built `<loki_url>/loki/api/v1/query_range` from it and sent a GET at the private level. That level admits each address but cloud metadata, whatever `ai.allow_private_network` says.

httpx2 replaces the query of the URL with the parameters of the query. So a URL such as `http://<host>/some/path?x=` became `GET /some/path?query=...`, with any path that the caller names.

The tool also returned the answer. The text of a non-200 answer went into the error of the tool. A 200 answer was parsed as Loki JSON, and its log lines went back to the model. So a model could send GET requests to the loopback and private services of the host and read what they answered.

The cause is the same as in #2480: input from a caller is used as configuration.

## What Changes

- The MCP tool `k8s_logs` publishes no `loki_url` option. It publishes `pod`, `query_arg`, `query`, `container`, `namespace`, `follow`, `tail`, `limit`, `since` and `dry_run`. A call that gives `loki_url` fails at the argument contract. It sends no request.
- The tool queries the Loki that `devops k8s logs` queries when a person gives no `--loki-url`. This is `DEFAULT_LOKI_URL`. The path of the request is always `/loki/api/v1/query_range`.
- `devops k8s logs` keeps `--loki-url` for a person at the command line.
- A consumer sees the tool schema and the requests, so the change carries a spec delta. It adds one requirement to the capability `k8s-logs`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-logs`: one new requirement, "The MCP tool k8s_logs publishes no Loki URL". It gives the tool schema, the refusal of a URL and the Loki that the tool queries.

## Impact

- `src/devops_cli/ai/mcp/generator.py`.
- `tests/test_k8s_logql.py`.
- `docs/MCP_TOOLS.md` (generated).
- `SECURITY.md` needs no change. Principle 11 already says that a tool publishes no option for a URL from a model.

## Feasibility

- On `origin/main` at `9f6ace18`, an offline probe showed the defect. It ran with `HOME` in a temporary directory, the null keyring and no `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK`. It bound an HTTP listener on `127.0.0.1` that answers HTTP 500 with a marker text. It called `k8s_logs` through a FastMCP `Client` with `query={namespace="a"}` and `loki_url=http://127.0.0.1:<port>/v1/sys/seal-status?x=`.
  - The listener got `GET /v1/sys/seal-status?query=%7Bnamespace%3D%22a%22%7D&limit=100&since=1h&direction=BACKWARD`.
  - The tool error held `Loki query failed with HTTP 500: <marker>`. The marker text came back to the caller.
- `k8s_logs` has no other Loki address. The settings hold no Loki key: `git log -S` finds no `loki.url` setting in the history, and `src/devops_cli/config/settings.py` has none. The command does not open a port-forward. Without `--loki-url`, `execute_logql_query` uses the constant `DEFAULT_LOKI_URL`, which is `http://localhost:3100`. If that Loki does not answer, it runs `kubectl logs`.
- `generate_mcp_tools` publishes each Click option of a command. `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` is the existing way to publish fewer options. #2480 uses it for the gateway tools. `ArgumentContractMiddleware` refuses a parameter that the published schema does not name.
- The exposure table `CONST_MCP_EXPOSURE_TABLE` holds `("k8s", "logs")` once. No other MCP tool and no hand-written tool in `src/devops_cli/ai/mcp/server.py` passes `--loki-url` to the command. The terminal dashboard calls `execute_logql_query` with a query and no URL.

## Existing Tool Considered

The change uses `_PATH_PARAM_RESTRICTIONS` of the MCP generator and the argument contract of the MCP server. Both exist, and #2480 and #2634 use both. No open tool decides which address a model may give. So the change builds no new function. It adds one entry to an existing table.

The change deletes the `loki_url` option of one MCP tool. It deletes the GET request to a host and path that a model names. It deletes the return of the answer text.
