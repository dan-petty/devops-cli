# Proposal

## Why

#2184: The egress checks of `src/devops_cli/core/validation.py` tell a public address from a non-public one with rules that devops-cli keeps by hand. The block list `CONST_PRIVATE_NETWORKS`, the offsets, `_embedded_ipv4s`, `_parse_ip`, `is_cloud_metadata_ip` and `is_private_ip` are a copy of the private module `pydantic_ai._ssrf`. That module has no API promise, so the copy can drift with each upgrade, and nothing shows it. Python's `ipaddress` follows the IANA special-purpose registries and is the maintained source for the address rules.

## What Changes

- Pin the answers first. Add `tests/core/test_non_public_ip_table.py`, a table test that passes on the base. It runs `is_non_public_ip` over the rows of the IANA IPv4 and IPv6 special-purpose registries, over multicast, and over the NAT64, Teredo, 6to4, IPv4-mapped, IPv4-compatible and ISATAP forms of non-public and public addresses. The row `64:ff9b::c000:201` (the NAT64 form of the documentation address 192.0.2.1) fails if a change drops the NAT64 rule.
- `is_private_ip` asks the standard library about each address it checks, which is the address and each IPv4 address that it embeds. An address is non-public when `is_global` is False, when `is_multicast` is True, or when it is in `192.0.0.0/24` (RFC 6890). `CONST_PRIVATE_NETWORKS` no longer decides a single address.
- Keep the rules that the standard library lacks, each with a comment that names the RFC and a row in the table: NAT64 (RFC 6052, RFC 8215), IPv4-compatible `::/96` (RFC 4291), ISATAP (RFC 5214) and the whole block `192.0.0.0/24`. Keep multicast through `is_multicast`. The NAT64 rule keeps every offset (48, 56, 64 and 96 bits).
- `_exhaustive_embedded_ipv4s` reads the Teredo client with `IPv6Address.teredo`. Delete `CONST_TEREDO_PREFIX`.
- `CONST_PRIVATE_NETWORKS` stays for two jobs: the overlap test of a range in `is_non_public_ip`, and the link-local networks. The standard library has no public list of its blocks, and `is_global` of a network looks at its two ends only. The table test holds the list to the standard library: both ends of each block are non-global, or the block is a documented exception.
- Change the docstring of `is_non_public_ip` in `src/devops_cli/core/validation.py` and the module docstring of `src/devops_cli/http/egress.py`. They name pydantic-ai as the source of the rules.
- Not in this change: the cloud metadata addresses and the offsets for the metadata check. The standard library has no list of them. The finish-reason maps at `src/devops_cli/config/constants.py:2731`. They are no address rule. The DNS seam of #1314, which is open.
- The change has no spec delta and sets `skip_specs: true` in `.openspec.yaml`. It is a refactor that keeps behavior: `is_non_public_ip` gives the same answer for every probe address (see Feasibility). No devops command, option or message changes, so no document is regenerated. The requirements of `sandbox-egress`, `configured-service-urls` and `public-api-egress` say nothing about how an address is classified, and they still hold. `is_private_ip` changes for one set of IPv6 addresses (for example `2002::/16`), which the standard library calls non-global. `is_non_public_ip` was already True for them, and it is the only caller of `is_private_ip` in `src/` (`validation.py:352`).
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/core/validation.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/http/egress.py` (one docstring).
- Tests: `tests/core/test_non_public_ip_table.py` (new).
- Callers that must keep their results: `is_non_public_ip` in `src/devops_cli/http/egress.py` (twice) and `src/devops_cli/sandbox/models.py:282`, `is_cloud_metadata_ip` in `src/devops_cli/http/egress.py:86`, and `is_loopback_or_private_host` in `src/devops_cli/core/validation.py`.
- Existing tests that must pass unchanged: `tests/core/test_validation.py`, `tests/core/test_numeric_hosts.py`, `tests/core/test_sandbox_policy_properties.py`, `tests/http`, `tests/security` and `tests/sandbox`.

## Feasibility

Checked on 2026-11-02 at main 24ef67ac, on Python 3.14.6 and pydantic-ai 2.59.0 (this container has no 3.14.10, the version in `.python-version`). The supported floor is Python 3.14 (`requires-python`, `pyproject.toml:10`).

- The premise holds. `git grep -n "CONST_PRIVATE_NETWORKS" -- src` finds the list at `src/devops_cli/config/constants.py:2803` and its two readers in `src/devops_cli/core/validation.py` (`_private_networks` at `:46` and the loop in `is_private_ip` at `:174`). `find_spec('pydantic_ai._ssrf')` finds the private module. Eight constants of that module (the private networks, the NAT64 offsets and prefixes, the ISATAP ids, the Teredo prefix, the all-offsets tuple and the two metadata sets) compare `==` to ours, and `_embedded_ipv4s`, `_parse_ip`, `is_cloud_metadata_ip` and `is_private_ip` have the same bodies.
- The issue is stale in two places. `_enforce_non_private_ssrf` and `validate_url` are gone (#2845, `6ebc9683`), and pydantic-ai is at 2.59.0, not 2.54.0. The line numbers of the issue are out of date, and this plan uses the lines of main.
- pydantic-ai has no public classifier. `pydantic_ai/_ssrf.py` sets `__all__ = ['safe_download']`, and `_ssrf` is imported only by `models/__init__.py` and `common_tools/web_fetch.py`.
- #2152 is closed as completed. #3128 merged it on 2026-11-01. `parse_numeric_ip` at `src/devops_cli/core/validation.py:194` now reads a legacy host with `getaddrinfo`. This change does not touch that function, so the two changes share no line.
- The standard library does not cover every rule. `is_global` is True for `64:ff9b::c000:201` (NAT64 of 192.0.2.1), for the NAT64 form of a 10.0.0.0/8 address, for `::a00:1` (IPv4-compatible), for `2606:4700::5efe:a00:1` (ISATAP), for `224.0.0.1` and `ff02::1` (multicast) and for `192.0.0.9` and `192.0.0.10`. `is_global` is False for the mapped form of an address in 10.0.0.0/8, `2002:a00:1::`, `2001:0:a9fe:a9fe::`, `64:ff9b:1::a00:1`, `100.64.0.1` and `3fff::1`.
- A plan that drops the NAT64 rule is wrong. A probe removed the NAT64 loop of `_standard_embedded_ipv4s`. `is_non_public_ip` then gave False for `64:ff9b::c000:201`, `64:ff9b::a00:1`, `64:ff9b::7f00:1` and `64:ff9b::a9fe:a9fe`, and `test_is_non_public_ip` and `test_pydantic_ai_ssrf_classifier_contract` in `tests/core/test_validation.py` failed. The probe also showed that the row `64:ff9b:1::/48` (RFC 8215) changes no answer, because `is_global` is False for that /48. The plan keeps the row, so the NAT64 rule stays whole.
- A range needs the list. `ipaddress.ip_network('8.0.0.0/5').is_global` and `ip_network('64::/16').is_global` are True, though the first holds 10.0.0.0/8 and the second holds `64:ff9b::/96`. `tests/core/test_validation.py` refuses both (`test_a_range_is_non_public_when_any_of_its_addresses_is`). The only list of blocks in the standard library is the private attribute `IPv4Address._constants._private_networks`, which would replace one private source with another.
- The single-address change keeps the answers. A probe script (under `.data/agent/scratch/`, not committed) compared `is_private_ip` of main with the same function on `not is_global or is_multicast or in 192.0.0.0/24`. The 58,242 addresses were the edges of every block of `CONST_PRIVATE_NETWORKS` and of the standard library, 40,000 random addresses, and the mapped, compatible, NAT64, ISATAP, 6to4 and local-use NAT64 forms of 3,000 IPv4 addresses. `is_non_public_ip` differed for 0 addresses. `is_private_ip` differed for 2,605 addresses, all IPv6 addresses that the standard library calls non-global, with no address going from True to False.
- The pinned tests pass with the probe. With the probe applied, `uv run pytest tests/core/test_validation.py tests/core/test_numeric_hosts.py tests/core/test_sandbox_policy_properties.py tests/http tests/security tests/sandbox -n4` gave 1932 passed, 1 skipped.
- Without the exception for `192.0.0.0/24`, `192.0.0.9` and `192.0.0.10` would become public: `is_global` is True for both, and main refuses them. The plan keeps them refused. A loosening in the egress guard is a decision for a person.
- Unverified: the `is_global` table of Python 3.14.10 and later patch releases. The table test pins the registry rows, so a release that changes one fails in CI.
- Nothing newer covers the work. A search of pull requests for 2184 finds only this plan. `git grep -n "is_non_public_ip\|CONST_PRIVATE_NETWORKS" -- openspec/changes` finds no active change but this one.

## Existing Tool Considered

Python's `ipaddress` (`is_global`, `is_multicast`, `ipv4_mapped`, `sixtofour`, `teredo`) is the open, maintained tool for the address rules, and the change uses it. It adds no dependency. It lacks four rules (NAT64, IPv4-compatible, ISATAP, and the whole block `192.0.0.0/24`) and a public list of its blocks. The change keeps the first four as small rules with RFC comments and a table row. It keeps the list for the overlap test of a range. The change writes about 40 lines of code and 150 lines of test. The cost is about 9,000 tokens to build and about 2 hours. It is about 400 tokens a year to keep, because the table test names the row that a release changes, and about 1,000 tokens for each correction. The status quo costs more: a diff of a private module on each pydantic-ai upgrade is about 4,000 tokens and 30 minutes, and nothing starts it.

The change deletes `CONST_TEREDO_PREFIX`, the loop over `CONST_PRIVATE_NETWORKS` in `is_private_ip`, and the claims in two docstrings that pydantic-ai is the source of a rule. It keeps `_non_public_networks`, `_exhaustive_embedded_ipv4s`, `_standard_embedded_ipv4s`, `_embedded_ipv4s`, `CONST_NAT64_PREFIXES`, `CONST_ALL_EMBEDDED_OFFSETS` and `CONST_IPV4_EMBEDDING_IPV6_PREFIXES`. The overlap test of a range reads `_non_public_networks` (`validation.py:350`), and `is_cloud_metadata_ip` reads `_exhaustive_embedded_ipv4s` (`validation.py:160`). The standard library has no replacement for either.
