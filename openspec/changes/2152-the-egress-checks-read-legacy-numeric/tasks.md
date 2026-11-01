# Tasks

## 1. The test doubles pass a call with AI_NUMERICHOST

Reads: `tests/web_fakes.py`, `tests/conftest.py`, `tests/security/test_reference_address_classes.py`, `tests/security/test_reference_extraction.py`. Changes: `tests/web_fakes.py`, `tests/security/test_reference_address_classes.py`, `tests/security/test_reference_extraction.py`.

- [ ] 1.1 This group edits tests only, so it has no test of its own. Its check is `uv run devops ci test tests/commands/test_sandbox_networking.py tests/http tests/security/test_reference_address_classes.py tests/security/test_reference_extraction.py`. The check passes on the base, before any edit, and it passes after each task of the group and after group 3. Run it on the base first
- [ ] 1.2 In `ScriptedResolver.__call__` of `tests/web_fakes.py`, send a call whose `flags` hold `socket.AI_NUMERICHOST` to `fallback` and do not count it as a lookup. Read the flags as `_guarded_getaddrinfo` in `tests/conftest.py` reads them. Change the docstring of the class to say so. A real resolver reads no name for such a call, and group 3 needs this: `test_the_whitelist_policy_looks_up_each_name_once` in `tests/commands/test_sandbox_networking.py` counts the lookups of each name. Then run the check of 1.1
- [ ] 1.3 In `test_a_network_target_names_the_address_a_resolver_would_dial` of `tests/security/test_reference_address_classes.py`, replace the stub `_no_lookup` with a stub that raises `AssertionError("no lookup may be made")` for a call without `AI_NUMERICHOST`, and passes a call with it to the `socket.getaddrinfo` that the test saved before it patched. Change the docstring to say that no DNS query is made. Then run the check of 1.1
- [ ] 1.4 In `test_reference_extraction_makes_no_dns_lookup` of `tests/security/test_reference_extraction.py`, change `exploding_getaddrinfo` in the same way. Then run the check of 1.1

## 2. The legacy spellings and the classifier branches have tests

Reads: `src/devops_cli/core/validation.py`, `tests/security/test_reference_address_classes.py`, `tests/core/test_validation.py`. Changes: `tests/core/test_numeric_hosts.py` (new), `tests/security/test_reference_address_classes.py`.

- [ ] 2.1 This group adds tests that describe the code as it is now, so they pass on the base and must not fail on the base. Its check is `uv run devops ci test tests/core/test_numeric_hosts.py tests/security/test_reference_address_classes.py`. The check passes on the base, after each task of the group and after group 3. Task 2.4 shows that each test can fail
- [ ] 2.2 Add the rows `("0177.0.0.1", "127.0.0.1")`, `("127.0.1", "127.0.0.1")`, `("http://0177.0.0.1/", "127.0.0.1")` and `("http://127.0.1/", "127.0.0.1")` to the parameters of `test_a_network_target_names_the_address_a_resolver_would_dial` in `tests/security/test_reference_address_classes.py`. That test already holds the rows `2130706433`, `127.1` and `0x7f.0.0.1`. Then run the check of 2.1
- [ ] 2.3 Create `tests/core/test_numeric_hosts.py`, in the style of `tests/core/test_validation.py`, with these tests. Each test has a docstring that cites #2152. Then run the check of 2.1
  - `parse_numeric_ip` gives the address for `0177.0.0.1`, `127.1`, `127.0.1`, `2130706433`, `0x7f.1`, `0x7f000001`, `017700000001` and `fe80::1%eth0`
  - `parse_numeric_ip` gives `None` for `08.0.0.1`, `1.2.3.4 x`, `256.1.1.1`, `example.com`, `"x" * 300` and `"é" * 70`. The last two make the C library raise `UnicodeError`
  - `is_loopback_host` and `is_loopback_or_private_host` give `True` for `0177.0.0.1` and `127.0.1`
  - `is_cloud_metadata_host("fe80::1%eth0")` and `is_loopback_or_private_host("fe80::1%eth0")` give `True`, as for a link-local address
  - `is_cloud_metadata_ip("fd00:ec2::254%eth0")` gives `True`, which needs the drop of the zone ID in `_parse_ip`
  - `is_private_ip("not-an-ip")` and `is_private_ip("")` give `True`
- [ ] 2.4 Run this check by hand, once, with the group committed, to show that each new test can fail. After each step run `uv run devops ci test tests/core/test_numeric_hosts.py tests/security/test_reference_address_classes.py`, see the failure that the step names, and run `git restore src/devops_cli/core/validation.py`
  1. In `parse_numeric_ip` of `src/devops_cli/core/validation.py`, change `return _parse_legacy_ipv4(host)` to `return None`. The rows of the octal, three-part and one-part forms fail, and so do the rows of `tests/security/test_reference_address_classes.py`
  2. In `_parse_ip` of the same file, delete the `if isinstance(ip, ipaddress.IPv6Address) and ip.scope_id is not None:` block with its body. The test of `is_cloud_metadata_ip("fd00:ec2::254%eth0")` fails
  3. In `is_private_ip` of the same file, change the `return True` after `if parsed is None:` to `return False`. The tests of a value that does not parse fail

## 3. parse_numeric_ip reads a host as the resolver does

Reads: `src/devops_cli/core/validation.py`, `src/devops_cli/security/reference_extractor.py`, `tests/core/test_numeric_hosts.py`. Changes: `src/devops_cli/core/validation.py`, `src/devops_cli/security/reference_extractor.py`, `tests/core/test_numeric_hosts.py`.

- [ ] 3.1 Write the failing test first in `tests/core/test_numeric_hosts.py`. `parse_numeric_ip` gives `None` for `0b11.1`, `0o17.1`, `+1.2.3.4`, `1_0.0.0.1`, `٣.0.0.1` and `127.0.0.1 ` with a trailing space, which a resolver reads as names. It gives `127.0.0.1` for `127。0。0。1`, which a resolver reads as that address. A second test patches `socket.getaddrinfo` with a recorder that calls the saved original, calls `parse_numeric_ip` for `0177.0.0.1` and for `example.com`, and asserts that each host made one call and that every call carries `socket.AI_NUMERICHOST`. Verify that `uv run devops ci test tests/core/test_numeric_hosts.py` fails on the base. The seven spellings fail because the old parser reads them differently, and the recorder test fails because the old parser makes no call
- [ ] 3.2 Rewrite `parse_numeric_ip` in `src/devops_cli/core/validation.py`. Return `ipaddress.ip_address(host)` when it parses. Else call `socket.getaddrinfo(host, None, flags=socket.AI_NUMERICHOST)`, give `answers[0][4][0]` to `ipaddress.ip_address`, and return it. Catch `(OSError, UnicodeError)` and return `None`. Delete `_parse_part`, `_combine_ipv4_parts` and `_parse_legacy_ipv4`. Change the docstring of `parse_numeric_ip`, which says "without getaddrinfo", and the sentence "Nothing is looked up." in the docstring of `network_target_address` in `src/devops_cli/security/reference_extractor.py` to say that no DNS query is made. Verify that `uv run devops ci test tests/core tests/security tests/http tests/commands/test_sandbox_networking.py tests/commands/test_valkey.py` passes. The run includes the existing tests of the one-part, two-part and hex forms in `tests/security/test_reference_address_classes.py`, `tests/security/test_builtin_tools.py` and `tests/security/test_vulnerability_lookup.py`
- [ ] 3.3 Verify that the three functions, and with them the two branches that could not run, are gone: `! git grep -n -e _parse_part -e _combine_ipv4_parts -e _parse_legacy_ipv4 -- src tests` prints nothing and exits 0
- [ ] 3.4 Verify the whole gate, the `constructs` row included: `uv run devops ci` passes
