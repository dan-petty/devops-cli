# Design

## Decisions

- **Use socket.getaddrinfo with AI_NUMERICHOST to parse legacy numeric IP hosts**: The C library's own rules handle all legacy forms correctly. The hermetic floor in tests/conftest.py:311-323 allows the call through. AGENTS.md and #1107 make a hand-rolled parser a defect.
- **Delete the repeated metadata check in _enforce_non_private_ssrf**: validate_url, its only caller, already performs the same check before calling _enforce_non_private_ssrf. The raise at line 614 cannot run and is dead code.
- **Delete the unreachable branches at lines 229 and 255-256**: Line 229 is excluded by the caller's 1-to-4 check. Lines 255-256 catch exceptions that _parse_legacy_ipv4 never raises. Both are dead code.

## Rejected alternatives

- **Use socket.inet_aton to parse legacy numeric IPs**: pyproject.toml:141-145 bans socket.inet_aton under TID251, citing #1107. The rule is active in the project.
- **Keep the hand-written parser and add the missing tests**: AGENTS.md rule 3 and #1107 make a hand-rolled address parser a defect. The project policy is to use the resolver's own parser, not a custom one.
