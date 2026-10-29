# Tasks

## 1. The MCP tool vault_status publishes no address

- [x] Add failing tests: the schema of `vault_status` holds only `dry_run`. A call that gives a loopback `vault_addr` fails, dials nothing and returns no value of an answer. A call with no address sends `GET /v1/sys/health` to the configured Vault. A call with no configured Vault fails and names both variables. `devops vault status --addr` still dials the address of the person
  - Verification: `uv run devops ci test tests/test_vault_cmd.py tests/test_fastmcp_contracts.py`
- [x] Give `("vault", "status")` an entry in `_PATH_PARAM_RESTRICTIONS` that leaves out `vault_addr`
  - Verification: `uv run devops ci test tests/test_vault_cmd.py tests/test_mcp.py tests/test_fastmcp_contracts.py`
- [x] Regenerate the tool documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. The broker refuses an address that changes the path

- [x] Add failing tests: an address with a query, or with a fragment, raises a configuration error. The error for a missing address names `VAULT_ADDR` and `DEVOPS_CLI_VAULT_ADDR` and no `--vault-addr`
  - Verification: `uv run devops ci test tests/test_vault_broker.py tests/test_vault_cmd.py`
- [x] Refuse `?` and `#` in the address of `VaultSecretBroker`, and fix the text of the missing-address error
  - Verification: `uv run devops ci test tests/test_vault_broker.py tests/test_vault_cmd.py tests/test_secret_resolution.py`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2639-mcp-vault-status-no-addr`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
