# Design

## Decisions

- **Ask `ipaddress` about each single address.** An address is non-public when `is_global` is False or `is_multicast` is True, or when it is in `192.0.0.0/24`. The same test runs on each IPv4 address that the address embeds. `ipaddress` follows the IANA registries and needs no copy. Evidence: on 58,242 probe addresses `is_non_public_ip` gave the same answer as main (Feasibility).
- **Keep the NAT64 rule whole, with the offsets of 48, 56, 64 and 96 bits.** `ipaddress` has no NAT64 property, and `is_global` is True for `64:ff9b::c000:201`, which embeds the documentation address 192.0.2.1. A probe that removed the rule made the NAT64 form of a private address public. Keep `CONST_NAT64_PREFIXES` as it is, both rows. The RFC 8215 row changes no answer today, because `is_global` is False for `64:ff9b:1::/48`. The plan does not remove a security rule on a redundancy that a table change of Python could end.
- **Keep the IPv4-compatible rule (RFC 4291) and the ISATAP rule (RFC 5214).** `is_global` is True for `::a00:1` and for `2606:4700::5efe:a00:1`, and `ipaddress` has no property for either. The RFC for ISATAP is 5214, which replaced RFC 4214, so the comment names 5214.
- **Add `is_multicast` and the block `192.0.0.0/24` as two documented rules.** `is_global` is True for `224.0.0.1` and `ff02::1`, so a multicast address needs its own test. IANA marks `192.0.0.9` and `192.0.0.10` as globally reachable, and main refuses them with the rest of the block. The block holds the Oracle Classic metadata address 192.0.0.192. The plan keeps the refusal, because it does not loosen the guard.
- **Use `IPv6Address.teredo` in the exhaustive decode.** It reads the same prefix `2001::/32` and the same inverted client address as the hand-written test. It removes `CONST_TEREDO_PREFIX`.
- **Keep `CONST_PRIVATE_NETWORKS` for the overlap test of a range and for the link-local networks.** A range is non-public when it holds one block. `is_global` of a network tests its two ends only, so `8.0.0.0/5` is global though it holds 10.0.0.0/8. `ipaddress` has no public list of blocks. The comment of the constant names the IANA registries as the source, not pydantic-ai. The table test holds each block to `is_global`, so the list cannot drift unseen. This is the check that AGENTS.md rule 11 asks for when an outside constraint blocks the fix.
- **Pin the answers before the change.** The table test passes on the base and on the changed code. Group 1 comes first, so a wrong answer of group 2 fails a named row.
- **Use an offline table test over `ipaddress` values.** The test reaches no network, no cluster and no scanner. It sits in `tests/core/`, the mirror of `src/devops_cli/core/`.
- **Name the Python floor.** The supported floor is Python 3.14 (`requires-python`). CI runs the pinned interpreter. The registry rows in the table fail the run if a release changes the `is_global` table for a row.
- **Write no spec delta.** No consumer-visible behavior changes. The rule of `openspec/config.yaml` for a refactor that keeps behavior applies.

## Rejected alternatives

- **Use `ipaddress` alone and delete the transition rules.** `is_global` is True for the NAT64, IPv4-compatible and ISATAP forms of a private address, and for multicast. The probe of Feasibility shows each case, and the NAT64 probe fails two existing tests.
- **Use `is_global` or `is_private` for a range.** `ip_network('8.0.0.0/5').is_global` and `ip_network('64::/16').is_global` are True, and `tests/core/test_validation.py` refuses both ranges.
- **Read the block list from `ipaddress._constants._private_networks`.** The attribute is private, so it has the same fault as `pydantic_ai._ssrf`.
- **Use the private module `pydantic_ai._ssrf` directly.** `pydantic_ai/_ssrf.py` sets `__all__ = ['safe_download']` at 2.59.0. It has no public classifier and no API promise.
- **Keep the hand-kept list and diff it on each upgrade.** Nothing starts the diff. The table test replaces it with a check that fails on its own.
- **Add `netaddr`.** `netaddr` 1.3.0 (BSD) publishes `IPV4_NOT_GLOBALLY_REACHABLE` (15 networks) and `IPV6_NOT_GLOBALLY_REACHABLE` (10 networks) as lists, which could replace the overlap list. It is not in `uv.lock`. Its `IPAddress('64:ff9b::c000:201').is_global()` is True, so the NAT64 rule stays. Its lists hold no multicast, and the overlap test would still loop over a list as today. A new dependency in the egress guard is a decision for a person, so the plan does not add it.
