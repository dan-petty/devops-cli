# Proposal

## Why

Issue #2639. The MCP tool `vault_status` published the option `vault_addr`. The model that calls the tool fills it in. `VaultSecretBroker.get_status` built `<vault_addr>/v1/sys/health` from it and sent a GET request at the private level. That level admits each address but cloud metadata, whatever `ai.allow_private_network` says. The request has no token.

An address that ends in `?x=` makes the path of the request the text that the caller wrote. `/v1/sys/health` is then only the value of the query. A fragment does the same: `http://<host>/some/path#` gives `GET /some/path`. The tool prints the `version` and `cluster_name` fields of a JSON answer. So a model could send a GET request to any path of any loopback or private service, and read two fields of the answer.

The cause is the same as in #2480: input from a caller is used as configuration.

## What Changes

- The MCP tool `vault_status` publishes no `vault_addr` option. It publishes only `dry_run`. A call that gives `vault_addr` fails at the argument contract. It sends no request.
- The tool asks the Vault that `VAULT_ADDR` or `DEVOPS_CLI_VAULT_ADDR` names, as `devops vault status` does when a person gives no `--addr`. The path of the request is always `/v1/sys/health`. With neither variable set, the call fails and the error names both.
- `devops vault status` keeps `--addr` for a person at the command line.
- `VaultSecretBroker` refuses an address that holds `?` or `#`. A person who sets such an address gets an error, and no request goes out. Defense in depth behind the primary fix: the address of a person can no longer change the path either.
- The error for a missing address no longer says `--vault-addr`. The option has never had that name, and only `devops vault status` has `--addr`.
- A consumer sees the tool schema and the requests, so the change carries a spec delta. It creates the capability `vault-status`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `vault-status`: three requirements. "The MCP tool vault_status publishes no address" gives the tool schema, the refusal of an address and the Vault that the tool asks. "The Vault address names the whole service" gives the refusal of a query or a fragment. "The command keeps its address option" keeps `--addr` for a person.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/security/vault_broker.py`.
- `tests/test_vault_cmd.py`, `tests/test_vault_broker.py`, `tests/test_fastmcp_contracts.py`.
- `docs/MCP_TOOLS.md` (generated).
- `SECURITY.md` needs no change. Principle 11 already says that a tool publishes no option for a URL or host from a model.

## Feasibility

- On `origin/main` at `9e8317bb`, a test with `scripted_resolver` and `record_connects` from `tests/web_fakes.py` showed the premise. The tool `vault_status` took `vault_addr` and the schema listed it. A call with `vault_addr="http://127.0.0.1:8200/some/path?x="` and `ai.allow_private_network` unset dialled `127.0.0.1:8200` and wrote `GET /some/path?x=/v1/sys/health`. The reply held the `version` and `cluster_name` values of the answer. The fail-to-pass run of this change repeats these results on the base tree.
- httpx2 2.13.1 shows the fragment case. For the address `http://h:8200/p#`, the request target is `/p`, because httpx2 drops the fragment and `/v1/sys/health` goes into it. A check of `urlsplit(addr).query` alone would miss it. `urlsplit("http://h/p#").fragment` is empty. So the check tests the characters `?` and `#`.
- The tool has no other address. `VaultSecretBroker(vault_addr=None)` reads `VAULT_ADDR`, then `DEVOPS_CLI_VAULT_ADDR`. The settings hold no Vault key, and the code has no default address. Without both variables the broker raises `VaultConfigurationError`, and the tool call fails with that message. A test shows it. This is the rule "config or an error that names the setting".
- The old error text said "or pass --vault-addr". The command has `--addr` and only on `status`. The test of the missing address showed the stale text on the base tree.
- `generate_mcp_tools` publishes each Click option of a command. `_PATH_PARAM_RESTRICTIONS` is the existing way to publish fewer options. #2480, #2634, #2635 and #2637 use it. `ArgumentContractMiddleware` refuses a parameter that the published schema does not name. The other Vault tools (`vault_get`, `vault_set`, `vault_sync`) already publish no address.
- `test_the_token_carrying_vault_tools_take_no_address` in `tests/test_fastmcp_contracts.py` said that `vault_status` takes an address because it sends no token. That reason is wrong: the request itself is the defect. The test now holds `vault_status` to the same rule.

## Existing Tool Considered

The change uses `_PATH_PARAM_RESTRICTIONS` of the MCP generator and the argument contract of the MCP server. Both exist, and #2480 and the later fixes use both. No open tool decides which address a model may give. So the change builds no new function. It adds one entry to an existing table and one condition to the address check of the broker. The condition tests two characters. A URL library cannot tell `http://h/p#` from `http://h/p`, so it covers no more than the condition.

The change deletes the `vault_addr` option of one MCP tool. It deletes the GET request to a host and path that a model names, and the stale `--vault-addr` text.
