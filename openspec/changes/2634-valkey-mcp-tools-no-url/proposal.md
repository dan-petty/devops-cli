# Proposal

## Why

Issue #2634. The MCP tools `valkey_ping`, `valkey_stats`, `valkey_info`, `valkey_get`, `valkey_set` and `valkey_flush` each published the option `url`. The model that calls the tool fills it in. `_resolve_client` built a `ValkeyClient` for that URL and gave it the Valkey password. The client dials at the private level, which admits each address but cloud metadata. valkey-py sends `AUTH <password>` when it connects.

A model could make devops-cli send the Valkey password to any host that it names. `valkey_set` and `valkey_flush` also wrote to that host. The cause is the same as in #2480: input from a caller is used as configuration.

## What Changes

- The six MCP tools publish no `url` option. Each tool dials the endpoint of `valkey.url` and sends the password only to it. A call that gives `url` fails at the argument contract. It opens no connection.
- The tools keep their other options: `section` for `valkey_info`, `key` for `valkey_get`, `key`, `value`, `ex` and `dry_run` for `valkey_set`, and `all_databases` and `dry_run` for `valkey_flush`.
- The nine `devops valkey` commands keep `--url` for a person at the command line. The password goes to the host that the person types. `SECURITY.md` records this accepted case under principle 11, and a test pins it.
- The shared fake `serving_valkey` returns at once when no client connects. A test of a refused call needs this. Before, the fake waited 30 seconds for a client that never came.
- A consumer sees the tool schemas and the connections, so the change carries a spec delta. It adds one requirement to the capability `valkey-endpoint`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `valkey-endpoint`: one new requirement, "The MCP Valkey tools publish no URL". It gives the tool schemas, the refusal of a URL and the endpoint that a tool dials.

## Impact

- `src/devops_cli/ai/mcp/generator.py`.
- `tests/test_valkey.py` and `tests/support/fakes/valkey.py`.
- `docs/MCP_TOOLS.md` (generated).
- `SECURITY.md` (one paragraph under principle 11) and `src/devops_cli/commands/valkey.py` (the docstring of `_resolve_client`).

## Feasibility

- On `origin/main` at `7dde54e8`, an offline probe showed the defect. It ran with `HOME` in a temporary directory, the null keyring and `DEVOPS_CLI_VALKEY_PASSWORD=FAKE-2634-value`. It bound a listener on `127.0.0.1` and called each tool through a FastMCP `Client`, with `url=valkey://127.0.0.1:<port>/0`.
  - `valkey_ping` sent `AUTH FAKE-2634-value`, two `CLIENT SETINFO` commands (valkey-py 6.2.0), and then `PING`.
  - `valkey_set` with `key=k` and `value=v` sent the same `AUTH`, and then `SET k v`.
  - `valkey_flush` sent the same `AUTH`, and then `FLUSHDB`.
- `generate_mcp_tools` publishes each Click option of a command. `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` is the existing way to publish fewer options, and #2480 uses it for the gateway tools. `ArgumentContractMiddleware` refuses a parameter that the published schema does not name.
- The exposure table `CONST_MCP_EXPOSURE_TABLE` holds six Valkey commands. `valkey keys`, `valkey backup` and `valkey cli` also take `--url`, but `tests/test_mcp.py` excludes them from MCP. The resource `resource://valkey/status` runs `valkey stats` with no URL.
- No other path gives a model a Valkey URL. No hand-written MCP tool in `src/devops_cli/ai/mcp/server.py` passes free arguments to a `devops` command.

## Existing Tool Considered

The change uses `_PATH_PARAM_RESTRICTIONS` of the MCP generator and the argument contract of the MCP server. Both exist and #2480 uses both. valkey-py has no option that sends a password only to one origin. So the change builds no new function. It adds six entries to an existing table.

The change deletes the `url` option of six MCP tools. It deletes the send of the Valkey password to a URL that a model gives. The one other edit is in the test fake `serving_valkey`: an accept loop that stops when no client connects.
