# Proposal

## Why

In #1373, `devops vault leases` listing and `--renew` do nothing in the one-shot CLI. The lease registry has no producer because DevOps CLI accesses only static KV secrets, and the in-memory registry lives for one process. In a long-lived process such as the MCP server, the registry keeps its first token forever and does not notice `devops vault login` or `devops vault logout`.

This change fits one pull request.

## What Changes

- Remove lease listing and the `--renew` flag from `devops vault leases`.
- Make `--revoke` the required operation for `devops vault leases` to revoke a lease ID against Vault.
- Move session lease registry tracking (`get_lease_registry` and `reset_lease_registry`) from `commands/vault.py` into `security/vault_lease.py`.
- Rebuild the session registry automatically when the broker address, token, or namespace changes.
- Reset the session registry when `devops vault logout` runs.
- Update documentation and tests to match the revoked-only lease lifecycle command.

This change carries a spec delta because command options and CLI invocation behavior change for consumers.

## Capabilities

### New Capabilities
- `vault-lease-lifecycle`: Revocation of Vault dynamic secret leases and session-scoped lease registry lifecycle management.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/commands/vault.py`: removes `_list_leases`, `_renew_leases`, and the `--renew` flag; requires `--revoke`; imports registry functions from `security/vault_lease.py`.
- `src/devops_cli/security/vault_lease.py`: exports `get_lease_registry` and `reset_lease_registry`, with automatic registry rebuilding on credential changes.
- `tests/conftest.py`: resets registry via `devops_cli.security.vault_lease`.
- `tests/test_vault_cmd.py` and `tests/test_secret_resolution.py`: tests for lease revocation and registry rebuilding.
- Documentation under `docs/commands/vault.md` and `docs/CLI_REFERENCE.md`.

## Feasibility

- Confirmed in `src/devops_cli/commands/vault.py` that `devops vault leases` with no flags or `--renew` accesses an empty in-memory registry created on demand.
- Confirmed with `uv run devops vault leases` and `uv run devops vault leases --renew` that the command always outputs 0 leases.
- Confirmed in `src/devops_cli/security/vault_broker.py` that secret retrieval only reads KV-v1 and KV-v2 endpoints (`_read_fields`), which produce no dynamic leases.
- Confirmed that Vault API endpoint `sys/leases/revoke` accepts single lease revocations with a valid client token.

## Existing Tool Considered

HashiCorp Vault native HTTP API endpoint `sys/leases/revoke` covers lease revocation. Internal code in `src/devops_cli/commands/vault.py` (`_list_leases`, `_renew_leases`, and `_LEASE_REGISTRY`) is deleted or moved to `src/devops_cli/security/vault_lease.py`.
