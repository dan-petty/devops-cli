# Design

## Context

See proposal.md for motivation. `commands/vault.py` currently holds `_LEASE_REGISTRY`, `get_lease_registry`, and `reset_lease_registry`. `devops vault leases` exposes listing, `--renew`, and `--revoke`.

## Goals / Non-Goals

**Goals:**
- Strip out dead listing and renewal operations from `devops vault leases`.
- Relocate session registry management into `src/devops_cli/security/vault_lease.py`.
- Rebuild the session registry whenever token, address, or namespace change.
- Reset the session registry during `devops vault logout`.

**Non-Goals:**
- Implementing dynamic secret engines (such as Vault database or AWS engines) in `devops-cli`.
- Adding persistent on-disk lease storage.

## Decisions

### 1. Require `--revoke` on `devops vault leases` and remove listing and `--renew`
`devops vault leases` now requires the `--revoke <lease_id>` option. Typer raises a usage error when the option is omitted.

- *Alternative Considered*: Build an on-disk SQLite or JSON lease cache and invent dynamic secret producers.
- *Evidence for Rejection*: DevOps CLI only queries static KV secrets. Building infrastructure for non-existent dynamic credentials violates AGENTS.md rule 3 and adds maintenance overhead for unused code.

### 2. Move registry helpers to `security/vault_lease.py`
`get_lease_registry` and `reset_lease_registry` move from `commands/vault.py` to `security/vault_lease.py`.

- *Alternative Considered*: Keep registry functions in `commands/vault.py`.
- *Evidence for Rejection*: ARCHITECTURE.md and #1332 require core security domain state to live under `security/`, keeping command modules focused on argument parsing and presentation.

### 3. Rebuild registry when credentials change
`get_lease_registry(default)` checks `vault_addr`, `token`, and `namespace` against the cached `_LEASE_REGISTRY`. If any property differs or no registry exists, it stores and returns `default`.

- *Alternative Considered*: Keep the first instantiated registry indefinitely.
- *Evidence for Rejection*: In long-lived processes like the FastMCP server, the initial token became stale after `devops vault login` or token rotation, causing subsequent calls to fail or use revoked credentials.

## Risks / Trade-offs

- [CLI Invocation Breaking Change] Users or scripts calling bare `devops vault leases` will receive a missing argument error. → Before 1.0.0, devops-cli does not keep backward compatibility for non-functional or misleading interfaces.
- [Leases in Old Registry Dropped on Token Change] Replacing `_LEASE_REGISTRY` drops existing leases tracked under the previous token. → A changed token invalidates previous lease ownership, so dropping stale leases is correct.
