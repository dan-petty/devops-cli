# Proposal

## Why

The message of `test_suppressions_stay_under_their_ceilings` named `src/devops_cli/config/defaults.py` as the home of the ceilings, and a higher ceiling as the first other fix. The ceilings are in the test file, and only the owner can allow a higher ceiling (#5253).

## What Changes

- The breach message names `tests/invariants/test_architectural_invariants.py:136`, where `DEFAULT_SUPPRESSION_CEILINGS` is.
- It names the usual fix for each kind first, from `_SUPPRESSION_FIXES`: for `[[tool.mypy.overrides]]`, the stub under `typings/`, as `typings/jq.pyi` does.
- It says that only the owner can allow a higher ceiling (AGENTS.md rule 5).
- Add the test `test_the_breach_message_names_the_ceiling_definition_and_the_fix`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The test message is not a behaviour of the product.

## Impact

- Tests: `tests/invariants/test_architectural_invariants.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. `DEFAULT_SUPPRESSION_CEILINGS` is at `tests/invariants/test_architectural_invariants.py:122` on main.
- `uv run pytest tests/invariants/test_architectural_invariants.py -k suppressions` passes after the change.

## Existing Tool Considered

The message is one f-string. No tool.

## Dependencies

None.
