# Proposal

## Why

devops config unset stops with a TypeError traceback when the target key is present only through a YAML merge key. The _find function in round_trip.py calls node.lc.key(dotted), which returns None for merged keys, and the code indexes into None. The user sees a traceback instead of a clear message, and the audit keeps reporting a secret that the command cannot remove. See #2656.

## What Changes

- Add a None check on node.lc.key(dotted) in _find before indexing, and raise ConfigurationError naming the file and stating the key comes from a merge key.
- Pass the name parameter from find into _find so the error message can name the file.
- Add a test that calls find with a merge-derived key and asserts ConfigurationError is raised with the expected message.
- Add a test that confirms direct key removal still works.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: merge-key-unset-reports-clear-error, direct-key-removal-is-unchanged

## Impact

None.

## Feasibility

- The premise is confirmed: src/devops_cli/config/round_trip.py line 161 reads int(node.lc.key(dotted)[0]) + 1 without checking for None. The issue cites the exact TypeError traceback at that line.
- ruamel.yaml resolves merge keys into the mapping so dotted in node is True, but the lc table holds no entry for a merged key, so lc.key(dotted) returns None. This is documented ruamel.yaml behavior.
- The fix is a None check and a raise in the existing _find function, plus passing name through. No new dependency is needed.
- First check: run uv run devops ci test tests/test_round_trip.py to confirm the new test fails before the fix and passes after.
- Second check: run uv run devops ci test to confirm no regression in the full suite.

## Existing Tool Considered

ruamel.yaml is already the project's round-trip YAML library. It lists merged keys in the mapping but gives no position for them, so node.lc.key() returns None. No external tool covers detecting a merge-derived key and reporting a friendly error. The fix is about 5 lines in the project's own round_trip.py: a None check and a raise. Written cost: roughly 10 tokens of new code, no new dependency, no ongoing maintenance beyond the existing module.
