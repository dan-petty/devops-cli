# Proposal

## Why

Issue #2462 reports that devops ai cost report exits 1 with ValueError: Invalid IPv6 URL when a spend ledger row holds a served_by value such as http://[::1. The function _is_single_server_local in src/devops_cli/ai/spend/pricing.py calls urlsplit(clean) with no guard. Legacy rows from before the extract_served_by write-time guard can hold such a value. The report must show the row and treat the backend as unknown instead of crashing.

## What Changes

- Wrap the urlsplit(clean) call in _is_single_server_local with a try-except ValueError that returns False on exception.
- Add a test that verifies _is_single_server_local returns False for http://[::1 without raising.
- Add a test that verifies is_local returns False for a served_by value that urlsplit cannot parse.
- Add a test that verifies a valid local served_by value such as http://localhost:11434 still resolves as local.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: Report does not crash on unparseable served_by, Unparseable backend shows as unknown, Valid served_by values still resolve

## Impact

- Code: `src/devops_cli/ai/spend/pricing.py`
- Tests: `tests/test_pricing.py`

## Feasibility

- The context shows _is_single_server_local at src/devops_cli/ai/spend/pricing.py line 243 calling urlsplit(clean) with no guard, matching the traceback in the issue.
- The context shows _is_local_host in the same file catching ValueError from ipaddress.ip_address, confirming the try-except pattern is established in this module.
- The context shows extract_served_by at src/devops_cli/ai/client/network.py line 99, confirming the write-time guard that prevents new rows from holding bad values.
- The archived design at openspec/changes/archive/2026-10-28-1110-reply-server-origin/design.md confirms the legacy row scenario and references #2462.
- First check: run uv run pytest tests/test_pricing.py -k unparseable -x to confirm the new test fails before the fix.
- Second check: run uv run pytest tests/test_pricing.py -x to confirm all pricing tests pass after the fix.

## Existing Tool Considered

No external tool covers this need. The fix is a try-except ValueError guard around one urlsplit call in src/devops_cli/ai/spend/pricing.py, plus tests. The written cost is roughly 5 lines of code and 20 lines of test. No new dependency is added. No internal code is deleted.
