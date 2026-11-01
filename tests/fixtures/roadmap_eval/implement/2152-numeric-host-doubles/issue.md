### What happened

The SSRF and egress checks in `core/validation.py` read legacy numeric hosts, such as `0177.0.0.1`, `127.1` and `2130706433`, with a parser that devops-cli wrote itself (`_parse_part`, `_combine_ipv4_parts`, `_parse_legacy_ipv4`). AGENTS.md and #1107 make a hand-rolled address parser a defect. Some of its forms and some classifier branches have no test, and two branches cannot run.

- No test sends an octal form (`0177.0.0.1`) or a three-part form (`127.0.1`). The one-part, two-part and hex forms have tests.
- No test checks that `is_private_ip` treats a value that does not parse as private, or that `_parse_ip` drops an IPv6 zone ID before it classifies the address.
- `_enforce_non_private_ssrf` checks for cloud metadata again, but `validate_url`, its only caller, makes the same check first. So the `raise` cannot run.
- `parse_numeric_ip` catches `OSError` and `ValueError` from `_parse_legacy_ipv4`, which raises neither. `_combine_ipv4_parts` has a `return None` for more than four parts that its only caller already excludes.

### What should happen

The legacy forms are read by the parser that the resolver itself uses. `socket.getaddrinfo(host, None, flags=socket.AI_NUMERICHOST)` parses a numeric host with the C library's own rules and makes no DNS query. The hermetic floor already lets this call through (`tests/conftest.py:311-323`). `ipaddress.ip_address` then classifies the result.

`socket.inet_aton` is not the answer: `pyproject.toml:141-145` bans it (TID251, #1107).

Checked on 2026-10-24 with Python 3.14.7 on glibc: `getaddrinfo` with `AI_NUMERICHOST` returns `127.0.0.1` for `0177.0.0.1`, `127.1`, `127.0.1`, `2130706433`, `0x7f.1` and `0x7f000001`, and refuses `08.0.0.1` and `1.2.3.4 x`.

### Evidence

At b170358e:
- `src/devops_cli/core/validation.py:198-256`: `_parse_part`, `_combine_ipv4_parts`, `_parse_legacy_ipv4` and `parse_numeric_ip`.
- `:140-148` and `:172-174`: the zone-ID drop and the unparsable-is-private default. Lines 144-147 and 174 were not covered in CI at f4d7066b.
- `:208` (octal) and `:224-225` (three parts) were not covered.
- `:612-617` (`_enforce_non_private_ssrf`) repeats the check at `:685-689` (`validate_url`). Line 614 was not covered.
- `:229` and `:255-256` cannot run.
- Callers: `core/validation.py:278`, `:311`, `:316`, `:476`; `security/reference_extractor.py:101`, `:103`.

### Acceptance criteria

- [ ] Tests first: `validate_url(..., allow_private=False)` and `is_loopback_or_private_host` refuse `http://0177.0.0.1/` and `http://127.0.1/`, and the classifier treats `fe80::1%eth0` as link-local. Each test fails on a parser that drops the form.
- [ ] A test shows that `is_private_ip` returns `True` for a value that does not parse.
- [ ] `parse_numeric_ip` reads legacy forms with `socket.getaddrinfo(..., flags=socket.AI_NUMERICHOST)` and `ipaddress`. `_parse_part`, `_combine_ipv4_parts` and `_parse_legacy_ipv4` are deleted. If #1314's DNS seam has landed, the call goes through it.
- [ ] The repeated metadata check in `_enforce_non_private_ssrf` and the unreachable branches at `:229` and `:255-256` are deleted.
- [ ] The existing tests of the one-part, two-part and hex forms (`tests/test_reference_extractor.py:138-140`, `tests/test_builtin_tools.py:307`) still pass.
- [ ] No test starts a program or makes a DNS query (docs/TESTING.md).
- [ ] `uv run devops ci` passes, the `constructs` row included.

Related: #1107 (the rule and the ban), #1314 (the DNS seam), #1381 (the egress-checked clients).


regression of #1107

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=ff475047a19fc30d0b22a97327311505d52d61bd -->
## Proposed design

### Problem statement
The SSRF and egress checks in core/validation.py parse legacy numeric IP hosts with a hand-written parser. AGENTS.md and issue #1107 make a hand-rolled address parser a defect. Some parser forms and classifier branches have no test, and two branches cannot run. The fix replaces the parser with socket.getaddrinfo and the AI_NUMERICHOST flag. This call uses the C library's own parsing rules and makes no DNS query.

### Acceptance criteria
- Criterion 1: validate_url and is_loopback_or_private_host refuse `http://0177.0.0.1/` and `http://127.0.1/`, and the classifier treats fe80::1%eth0 as link-local.
  Verification: Each test fails on a parser that drops the form. Run uv run pytest tests/test_reference_extractor.py tests/test_builtin_tools.py.
- Criterion 2: is_private_ip returns True for a value that does not parse.
  Verification: Run the new test with uv run pytest -k is_private_ip.
- Criterion 3: parse_numeric_ip reads legacy forms with socket.getaddrinfo and ipaddress. The functions _parse_part, _combine_ipv4_parts and _parse_legacy_ipv4 are deleted.
  Verification: Run uv run pytest tests/test_reference_extractor.py tests/test_builtin_tools.py. Confirm the three functions are absent from src/devops_cli/core/validation.py.
- Criterion 4: The repeated metadata check in _enforce_non_private_ssrf and the unreachable branches are deleted.
  Verification: Confirm the repeated check and the unreachable return None are absent from src/devops_cli/core/validation.py.
- Criterion 5: The existing tests for one-part, two-part and hex forms still pass.
  Verification: Run uv run pytest tests/test_reference_extractor.py tests/test_builtin_tools.py -k 'numeric or ip'.
- Criterion 6: No test starts a program or makes a DNS query.
  Verification: The hermetic floor in tests/conftest.py fails a test that starts a program or makes an external DNS lookup.
- Criterion 7: uv run devops ci passes, including the constructs row.
  Verification: Run uv run devops ci and confirm all checks pass.

### Key questions
- **Can socket.getaddrinfo with AI_NUMERICHOST parse all legacy numeric IP forms without a DNS query?**: Yes. Verified on Python 3.14.7 on glibc: it returns 127.0.0.1 for 0177.0.0.1, 127.1, 127.0.1, 2130706433, 0x7f.1 and 0x7f000001, and refuses 08.0.0.1 and 1.2.3.4 x. [sources: tests/conftest.py:311-323]
- **Is socket.inet_aton available as an alternative parser?**: No. pyproject.toml bans it under TID251 (issue #1107). [sources: pyproject.toml:141-145]
- **Does the hermetic floor allow socket.getaddrinfo with AI_NUMERICHOST in tests?**: Yes. The guarded_getaddrinfo in tests/conftest.py lets the call through when the AI_NUMERICHOST flag is set. [sources: tests/conftest.py:311-323]
- **Should the getaddrinfo call go through the DNS seam from issue #1314?**: If #1314's DNS seam has landed, the call goes through it. Otherwise, call socket.getaddrinfo directly. (proposed)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->
