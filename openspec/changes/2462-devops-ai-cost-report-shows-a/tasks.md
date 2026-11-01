# Tasks

## 1. Guard urlsplit in _is_single_server_local and add tests

Reads: none. Changes: `src/devops_cli/ai/spend/pricing.py`, `tests/test_pricing.py`.

- [ ] 1.1 Write a test that calls _is_single_server_local with the string http://[::1 and a _SettingsOnce instance, and asserts it returns False without raising ValueError. Write a test that calls is_local with served_by set to http://[::1 and asserts it returns False. Write a test that calls is_local with served_by set to http://localhost:11434 and asserts it returns True, and verify that `uv run pytest tests/test_pricing.py -x` fails on the base
- [ ] 1.2 In _is_single_server_local, split the existing if clean in CONST_LOCAL_TRANSPORT_LABELS or urlsplit(clean).scheme == "http+unix" line into two checks. Keep the CONST_LOCAL_TRANSPORT_LABELS check as-is. Wrap the urlsplit(clean).scheme == "http+unix" check in a try block that catches ValueError and returns False, and verify that `uv run pytest tests/test_pricing.py -x` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
