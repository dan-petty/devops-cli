# Proposal

## Why

The network references table colors a safe low-risk reference red because the status text '✓ Safe / Low Risk' holds the substring 'RISK'. The condition on line 214 of `src/devops_cli/output/formatters/tables.py` does not exclude 'LOW'. Issue #2646.

## What Changes

- Change the red-color condition in `format_network_references_table` to exclude 'LOW' from the RISK check, matching the pattern in `reference_extractor.py`.
- Add a test that verifies 'Low Risk' renders green, 'High Risk' renders red, and 'Unchecked' renders yellow.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `console-output`: Safe low-risk status renders green, Flagged status renders red, Unchecked status renders yellow

## Impact

- Code: `src/devops_cli/output/formatters/tables.py`
- Tests: `tests/output/test_network_table_color.py`

## Feasibility

- The issue premise is confirmed: line 214 of `src/devops_cli/output/formatters/tables.py` checks `'RISK' in status_text` without excluding 'LOW'.
- The pattern in `src/devops_cli/security/reference_extractor.py` line 609 already handles this: `('RISK' in s and 'LOW' not in s)`.
- First check: run the reproduction command from the issue to confirm the red color.
- Second check: run the new test to confirm green for 'Low Risk' and red for 'High Risk'.

## Existing Tool Considered

No external tool or library covers this need. The fix is a one-line change to a string condition in the project's own code. The written cost is the tokens to edit one condition, add one test case, and verify the output.
