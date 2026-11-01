# Tasks

## 1. Add tests for legacy numeric IP forms and classifier edge cases

Reads: none. Changes: `tests/test_reference_extractor.py`.

- [ ] 1.1 Write tests: validate_url with allow_private=False refuses http://0177.0.0.1/ and http://127.0.1/; is_loopback_or_private_host treats fe80::1%eth0 as link-local; is_private_ip returns True for a value that does not parse as an IP address, and verify that `uv run pytest tests/test_reference_extractor.py -k 'octal or three_part or zone_id or unparsable'` fails on the base
- [ ] 1.2 Add test functions to tests/test_reference_extractor.py. Each test calls the public API with the specified input and asserts the expected refusal or classification. The tests pin the behavior before the implementation changes, and verify that `uv run pytest tests/test_reference_extractor.py -k 'octal or three_part or zone_id or unparsable'` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Replace hand-written IPv4 parser with getaddrinfo and delete dead code

Reads: none. Changes: `src/devops_cli/core/validation.py`.

- [ ] 2.1 The tests added in the previous group and the existing tests in tests/test_reference_extractor.py and tests/test_builtin_tools.py must all pass after the change, and verify that `uv run pytest tests/test_reference_extractor.py tests/test_builtin_tools.py` fails on the base
- [ ] 2.2 Rewrite parse_numeric_ip: first try ipaddress.ip_address(host); on ValueError, call socket.getaddrinfo(host, None, flags=socket.AI_NUMERICHOST) and pass results[0][4][0] to ipaddress.ip_address; catch OSError and return None. Delete _parse_part, _combine_ipv4_parts, and _parse_legacy_ipv4. Delete the repeated cloud-metadata check in _enforce_non_private_ssrf since validate_url already performs it, and verify that `uv run pytest tests/test_reference_extractor.py tests/test_builtin_tools.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
