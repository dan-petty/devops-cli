# Proposal

## Why

#2152: The SSRF and egress checks in core/validation.py parse legacy numeric IP hosts with a hand-written parser. AGENTS.md and #1107 make a hand-rolled address parser a defect. Some parser forms and classifier branches have no test, and two branches cannot run.

## What Changes

- Add tests for octal, three-part, zone-ID, and unparsable-is-private forms of legacy numeric IPs
- Replace parse_numeric_ip to use socket.getaddrinfo with AI_NUMERICHOST and ipaddress
- Delete _parse_part, _combine_ipv4_parts, and _parse_legacy_ipv4
- Delete the repeated metadata check in _enforce_non_private_ssrf
- Delete the unreachable return None and unreachable except clause
- Add spec requirements for numeric-host-parsing, unparsable-host-is-private, and ipv6-zone-id-stripped to public-api-egress
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `public-api-egress`: numeric-host-parsing, unparsable-host-is-private, ipv6-zone-id-stripped

## Impact

- Code: `src/devops_cli/core/validation.py`
- Tests: `tests/test_reference_extractor.py`

## Feasibility

- The issue confirms socket.getaddrinfo with AI_NUMERICHOST returns 127.0.0.1 for 0177.0.0.1, 127.1, 127.0.1, 2130706433, 0x7f.1, and 0x7f000001 on Python 3.14.7/glibc, and refuses 08.0.0.1 and 1.2.3.4 x (checked 2026-10-24).
- The hermetic floor in tests/conftest.py:311-323 lets getaddrinfo through when the AI_NUMERICHOST flag is set, so tests can call it without a DNS query.
- pyproject.toml:141-145 bans socket.inet_aton under TID251 (#1107), confirming getaddrinfo is the sanctioned path.
- First checks the implementation runs: uv run pytest tests/test_reference_extractor.py tests/test_builtin_tools.py -k 'numeric or ip' to confirm existing tests pass before and after the change; uv run devops ci to confirm the full gate including the constructs row passes.

## Existing Tool Considered

socket.getaddrinfo with the AI_NUMERICHOST flag is the stdlib tool that parses a numeric host with the C library's own rules and makes no DNS query. No external library is needed. The change deletes the internal code _parse_part, _combine_ipv4_parts, and _parse_legacy_ipv4 in src/devops_cli/core/validation.py.
