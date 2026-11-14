# Proposal

## Why

A public whitelist entry that is an IPv6 CIDR, such as `2606:4700::/48`, fails config validation. `_validate_public_whitelist_item` gives the CIDR string to `is_loopback_or_private_host`, which reads a CIDR as a name that is not public. The CIDR branch of `_resolve_public_host`, which handles the entry correctly, never runs (#3776).

## What Changes

- `_validate_public_whitelist_item` parses an IP literal first. It refuses the entry when `is_cloud_metadata_host` or `is_non_public_ip` holds, and accepts a public IPv6 address or CIDR.
- A name still goes to `is_loopback_or_private_host`, so the validator keeps its no-lookup promise.
- Tests cover a public IPv6 CIDR, a CIDR with host bits, a public IPv6 address, private IPv6 entries, a name with no lookup, and the command.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sandbox-egress`: The public whitelist validator accepts a public IP literal, IPv6 included.

## Impact

- Code: `src/devops_cli/sandbox/models.py`
- Tests: `tests/sandbox/test_sandbox_network_config.py`, `tests/commands/test_sandbox_network_policy.py`

## Feasibility

- `ipaddress.ip_network(..., strict=False)` parses the entry, and `is_non_public_ip` and `is_cloud_metadata_host` already classify a network.
- `_resolve_public_host` uses the same two checks, so the validator and the builder agree.
- Verification commands: `uv run devops ci test tests/sandbox/test_sandbox_network_config.py tests/commands/test_sandbox_network_policy.py`, the command with `2606:4700::/48`, and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The standard library `ipaddress` module parses and classifies the entry, and the module already imports it. The repository keeps its cloud-metadata check, which `ipaddress` does not give. No new dependency.
