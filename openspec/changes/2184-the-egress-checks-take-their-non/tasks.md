# Tasks

## 1. Add the table test and the standard-library classifier

Reads: `src/devops_cli/core/validation.py`, `src/devops_cli/config/constants.py`. Changes: `src/devops_cli/core/validation.py`, `tests/test_validation_non_public.py` (new).

- [ ] 1.1 Write a failing table test in `tests/test_validation_non_public.py` that asserts `is_non_public_ip` for the IANA IPv4 and IPv6 special-purpose registries and for the NAT64, Teredo, IPv4-mapped, ISATAP and IPv4-compatible forms, and verify that `uv run devops ci test tests/test_validation_non_public.py` fails on the base
- [ ] 1.2 Write the table test first. Replace `_non_public_networks`, `_exhaustive_embedded_ipv4s`, `_standard_embedded_ipv4s` and `_embedded_ipv4s` with a classifier that uses `ipaddress` `is_global`, `ipv4_mapped`, `sixtofour` and `teredo`. Keep the ISATAP interface-ID rule (RFC 4214) and the IPv4-compatible low-32-bit rule (RFC 4291), each with a comment and a test. Remove the imports of the deleted constants, and verify that `uv run devops ci test tests/test_validation_non_public.py` passes

## 2. Delete the copied block-list constants

Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/core/validation.py`. Changes: `src/devops_cli/config/constants.py`.

- [ ] 2.1 Delete `CONST_PRIVATE_NETWORKS`, `CONST_NAT64_PREFIXES`, `CONST_TEREDO_PREFIX`, `CONST_IPV4_EMBEDDING_IPV6_PREFIXES` and `CONST_ALL_EMBEDDED_OFFSETS` from `src/devops_cli/config/constants.py`. Keep `CONST_ISATAP_INTERFACE_IDS` and `CONST_LOW32_OFFSETS` with comments that name RFC 4214 and RFC 4291, and verify that `! git grep -n -E 'CONST_PRIVATE_NETWORKS|CONST_NAT64_PREFIXES|CONST_TEREDO_PREFIX|CONST_IPV4_EMBEDDING_IPV6_PREFIXES|CONST_ALL_EMBEDDED_OFFSETS' src/ tests/` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
