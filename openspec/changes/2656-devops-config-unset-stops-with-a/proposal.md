# Proposal

## Why

Issue #2656: devops config unset stops with a TypeError traceback when the config file gives the key through a YAML merge key. The _find function in round_trip.py calls node.lc.key(dotted), which returns None for merged keys, and the code indexes into None. The user sees a traceback instead of a clear message, and the audit keeps reporting a secret that the command cannot remove.

## What Changes

- Add a None check for node.lc.key(dotted) in _find in src/devops_cli/config/round_trip.py
- Raise a ConfigurationError naming the file and stating the key comes from a YAML merge key
- Pass the name parameter from find into _find so the error can name the file
- Add a test that calls find with a merge-derived key and asserts a ConfigurationError
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: merge-key-unset-reports-clear-error, direct-key-removal-unchanged

## Impact

None.

## Feasibility

- The premise is confirmed: src/devops_cli/config/round_trip.py line 161 shows int(node.lc.key(dotted)[0]) + 1, which raises TypeError when node.lc.key(dotted) returns None for a merged key.
- ConfigurationError is already imported in the module (from devops_cli.exceptions import ConfigurationError), so no new import is needed.
- The name parameter is available in find and can be passed to _find without changing the public API.
- First checks: run uv run devops ci test tests/test_round_trip.py to confirm existing tests pass, then run the new merge-key test to confirm the fix.

## Existing Tool Considered

The project already uses ruamel.yaml for round-trip YAML editing. ruamel.yaml lists merged keys as keys of the mapping but gives no position for them, so node.lc.key() returns None. No external tool covers the need to detect a merge-derived key and report a friendly error. The fix is a few lines in the project's own round_trip.py: check whether node.lc.key(dotted) is None before indexing, and raise a ConfigurationError. Written cost: roughly 10 tokens of new code, no new dependency, no ongoing maintenance beyond the existing module.
