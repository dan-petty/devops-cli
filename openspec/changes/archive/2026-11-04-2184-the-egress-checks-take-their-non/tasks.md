# Tasks

## 1. A table test pins the answers of the classifier

Reads: `src/devops_cli/core/validation.py`, `src/devops_cli/config/constants.py`, `tests/core/test_validation.py`. Changes: `tests/core/test_non_public_ip_table.py` (new).

- [x] 1.1 This group edits tests only, so it has no failing test. It adds a table test that passes on the base. Create `tests/core/test_non_public_ip_table.py` with a docstring that cites #2184. It has a parametrized test of `is_non_public_ip` with one row for each block of the IANA IPv4 and IPv6 special-purpose registries (the network address, the broadcast address and a middle address), for multicast (`224.0.0.1`, `ff02::1`), and for the forms below, each as a non-public row and a public row. NAT64: `64:ff9b::c000:201` (192.0.2.1), a NAT64 form of an address in 10.0.0.0/8, and `64:ff9b::808:808`. RFC 8215: `64:ff9b:1::808:808`. Teredo: `2001:0:a9fe:a9fe::`. 6to4: `2002:a9fe:a9fe::`. IPv4-mapped: `::ffff:8.8.8.8` and a mapped address in 10.0.0.0/8. IPv4-compatible: `::808:808` and `::a00:1`. ISATAP: `2606:4700::5efe:808:808` and `2606:4700::5efe:a00:1`. The block `192.0.0.0/24`: `192.0.0.9` and `192.0.0.10` are non-public, though `is_global` is True for both. Addresses that IANA marks globally reachable are public rows: `192.31.196.1`, `192.52.193.1`, `192.175.48.1`, `192.88.99.1`, `2001:1::1`, `2001:3::1`, `2001:4:112::1`, `2001:20::1` and `2620:4f:8000::1`. The expected answer of each row is the answer that main gives. A second parametrized test takes each block of `CONST_PRIVATE_NETWORKS` and asserts that `is_non_public_ip` of the block is True and that both ends of the block are non-global in `ipaddress`, except the two multicast blocks, which the test lists with the reason that `is_global` is True for them. A third test asserts that `is_non_public_ip` gives True for `8.0.0.0/5` and `64::/16` and False for `2606:4700::/48`. Then verify that `uv run devops ci test tests/core/test_non_public_ip_table.py` passes on the base, before any edit of `src/`. Show that the NAT64 rows can fail: delete the loop `for prefix, offsets_list in CONST_NAT64_PREFIXES:` in `_standard_embedded_ipv4s` by hand, see the NAT64 rows fail, and run `git restore src/devops_cli/core/validation.py`

## 2. The single-address check asks the standard library

Reads: `src/devops_cli/core/validation.py`, `src/devops_cli/config/constants.py`, `tests/core/test_non_public_ip_table.py`. Changes: `src/devops_cli/core/validation.py`, `src/devops_cli/config/constants.py`.

- [x] 2.1 Add `CONST_IETF_PROTOCOL_ASSIGNMENTS` (`192.0.0.0/24`, RFC 6890) to `src/devops_cli/config/constants.py`, with a comment that says IANA marks `192.0.0.9` and `192.0.0.10` as globally reachable and that the code refuses the whole block. In `is_private_ip` of `src/devops_cli/core/validation.py`, replace the loop over `CONST_PRIVATE_NETWORKS` with a test that is True when `is_global` is False, when `is_multicast` is True, or when an IPv4 address is in that constant, run on the address and on each address of `_embedded_ipv4s(parsed, exhaustive=False)`. In `_exhaustive_embedded_ipv4s`, read the Teredo client with `ip.teredo`, and delete `CONST_TEREDO_PREFIX` and its import. Put an RFC comment on the NAT64 loop (RFC 6052, RFC 8215), on the IPv4-compatible branch (RFC 4291 section 2.5.5.1) and on the ISATAP branch (RFC 5214), each with the reason that `ipaddress` lacks the rule. Change the comment above `CONST_PRIVATE_NETWORKS` to say that it is the list of IANA special-purpose blocks for the overlap test of a range and for the link-local networks, and why `ipaddress` cannot replace it. Keep `_non_public_networks`, `_exhaustive_embedded_ipv4s`, `_standard_embedded_ipv4s`, `_embedded_ipv4s`, `CONST_NAT64_PREFIXES` and `CONST_ALL_EMBEDDED_OFFSETS`, which `is_non_public_ip` and `is_cloud_metadata_ip` still read. Verify that `uv run devops ci test tests/core/test_non_public_ip_table.py tests/core/test_validation.py tests/core/test_numeric_hosts.py tests/core/test_sandbox_policy_properties.py tests/http tests/security tests/sandbox` passes

## 3. No docstring names a private module as the source of a rule

Reads: `src/devops_cli/core/validation.py`, `src/devops_cli/http/egress.py`. Changes: `src/devops_cli/core/validation.py`, `src/devops_cli/http/egress.py`.

- [x] 3.1 In the docstring of `is_non_public_ip` in `src/devops_cli/core/validation.py`, replace "one of pydantic-ai's non-public blocks" with "one of the special-purpose blocks of `CONST_PRIVATE_NETWORKS`". In the module docstring of `src/devops_cli/http/egress.py`, replace "pydantic-ai's `is_cloud_metadata_ip`" with "`is_cloud_metadata_ip` of `devops_cli.core.validation`". Verify that `! git grep -n -e CONST_TEREDO_PREFIX -e "pydantic-ai's non-public" -e "pydantic-ai's .is_cloud_metadata_ip" src/ tests/` passes

## Criteria

- No constant or docstring in `src/` copies or mirrors a private module of another package.: pending-person, group 3 removes the two docstring claims and group 2 re-sources the block list, but the grep of the issue also finds the comment at `src/devops_cli/config/constants.py:2731`, which says that the finish-reason maps copy private maps of pydantic-ai. Those maps are no address rule, and a person decides whether another issue covers them
- A table test runs the classifier over the IPv4 and IPv6 special-purpose registries of IANA and over the NAT64, Teredo and IPv4-mapped forms of private addresses, and each answer agrees with the chosen source or with a rule that the code documents.: group 1
- The existing SSRF tests pass unchanged.: group 2

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
