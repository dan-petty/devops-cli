# Design

## Context

`_parse_whitelist_entry` returns the address, CIDR or name of an entry. `_validate_public_whitelist_item` sends the host to `is_loopback_or_private_host`, which parses an address but not a CIDR. The policy builder's `_resolve_public_host` already parses a CIDR with `ipaddress.ip_network(host, strict=False)` and refuses a metadata or non-public network.

## Goals

- Accept a public IPv4 or IPv6 address or CIDR.
- Refuse a metadata, private, loopback or link-local IP literal.
- Keep the validator free of DNS lookups.

## Decisions

- **Parse the literal first.** The validator tries `ipaddress.ip_network(host, strict=False)`. A failed parse means a name, and only then does it call `is_loopback_or_private_host`.
- **The same two checks as the builder.** A parsed network is refused when `is_cloud_metadata_host` or `is_non_public_ip` holds. The two call sites cannot drift.
- **One message.** The existing "cannot be private, loopback, or metadata" text stays, so a caller sees the same error for an address, a CIDR and a name.

## Risks

- `is_non_public_ip` refuses a range that is not global, so a public CIDR passes only when both ends are global. That is the rule the builder already applies.

## Tests

- A public IPv6 CIDR, a CIDR with host bits, and a bare IPv6 address each give one `ipBlock` on TCP 443.
- `fd00::/8`, `::1/128`, `fe80::/10` and `fd00:ec2::254` are refused.
- A name is refused with no DNS lookup.
- The command prints the `ipBlock` and exits 0.
